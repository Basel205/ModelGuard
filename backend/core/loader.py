"""
loader.py — Secure Model Loader

This is the cryptographic gate between a model file and execution.
No model runs without passing verification.

Loading flow:
    model file + artifact
        → hash verification
        → merkle verification
        → threshold signature verification
        → policy check
        → revocation check
        → ALLOW or BLOCK execution

Inference-time verification:
    Every k inferences, randomly sample chunks and verify
    them using O(log N) Merkle proofs. Catches post-load
    memory tampering attacks.
"""

import time
import random
from pathlib import Path
from typing import Optional, Tuple, Dict
from dataclasses import dataclass, field

import torch
import torch.nn as nn

from ..crypto.signer import ModelSigner
from ..crypto.hasher import hash_cache, compare_hashes, hash_model_weights
from .policy import PolicyEngine, PolicyConfig
from .ledger import TamperEvidentLedger


# ── Load Result ───────────────────────────────────────────────────────────────

@dataclass
class LoadResult:
    """
    Result of a secure model load attempt.
    Always inspect .allowed before using the model.
    """
    allowed:          bool
    reason:           str
    model:            Optional[nn.Module]  = None
    artifact:         Optional[dict]       = None
    verification:     dict                 = field(default_factory=dict)
    policy_report:    dict                 = field(default_factory=dict)
    load_time_ms:     float                = 0.0

    def __bool__(self):
        return self.allowed


# ── Inference Guard ───────────────────────────────────────────────────────────

class InferenceGuard:
    """
    Wraps a verified model and enforces periodic integrity
    checks during inference.

    Every k inferences, randomly samples chunks and verifies
    them using O(log N) Merkle proofs.

    If verification fails mid-inference, execution is halted.
    """

    def __init__(
        self,
        model:            nn.Module,
        artifact:         dict,
        signer:           ModelSigner,
        verify_every:     int  = 10,    # verify every k inferences
        chunks_per_check: int  = 3,     # how many random chunks to sample
    ):
        self.model            = model
        self.artifact         = artifact
        self.signer           = signer
        self.verify_every     = verify_every
        self.chunks_per_check = chunks_per_check
        self._inference_count = 0
        self._chunk_count     = artifact["merkle_tree"]["chunk_count"]

    def __call__(self, *args, **kwargs):
        """Run inference with automatic integrity checking."""
        self._inference_count += 1

        # Periodic check
        if self._inference_count % self.verify_every == 0:
            self._verify_random_chunks()

        return self.model(*args, **kwargs)

    def _verify_random_chunks(self):
        """
        Sample random chunks and verify each one via Merkle proof.
        O(k * log N) where k = chunks_per_check, N = total chunks.
        Raises RuntimeError if any chunk fails.
        """
        state_dict    = self.model.state_dict()
        sample_size   = min(self.chunks_per_check, self._chunk_count)
        chunk_indices = random.sample(range(self._chunk_count), sample_size)

        for idx in chunk_indices:
            ok, reason = self.signer.verify_chunk_only(
                state_dict, self.artifact, idx
            )
            if not ok:
                raise RuntimeError(
                    f"SECURITY ALERT: Inference halted — "
                    f"chunk {idx} failed verification: {reason}"
                )

    def get_stats(self) -> dict:
        return {
            "inference_count":  self._inference_count,
            "verify_every":     self.verify_every,
            "chunks_per_check": self.chunks_per_check,
            "total_chunks":     self._chunk_count,
            "next_check_at":    self._inference_count + (
                self.verify_every - self._inference_count % self.verify_every
            ),
        }


# ── Secure Loader ─────────────────────────────────────────────────────────────

class SecureModelLoader:
    """
    Main secure loading interface.

    Usage:
        loader = SecureModelLoader(signer, policy_engine, ledger)
        result = loader.load("model.pt", "model.artifact.json", ModelClass)

        if result:
            guard = loader.wrap_for_inference(result)
            output = guard(input_tensor)
        else:
            print(result.reason)  # blocked — here's why
    """

    def __init__(
        self,
        signer:        ModelSigner,
        policy_engine: Optional[PolicyEngine] = None,
        ledger:        Optional[TamperEvidentLedger] = None,
    ):
        self.signer        = signer
        self.policy_engine = policy_engine or PolicyEngine()
        self.ledger        = ledger

    def load(
        self,
        model_path:    str,
        artifact_path: str,
        model_class:   type,
        device:        str = "cpu",
    ) -> LoadResult:
        """
        Securely load a model — full verification pipeline.

        Args:
            model_path:    path to .pt model file
            artifact_path: path to .json signed artifact
            model_class:   the nn.Module class to instantiate
            device:        torch device

        Returns:
            LoadResult — check .allowed before using .model
        """
        start_time = time.time()

        # ── Step 1: Load artifact ─────────────────────────────────────────────
        try:
            artifact = self.signer.load_artifact(artifact_path)
        except Exception as e:
            return LoadResult(
                allowed  = False,
                reason   = f"Could not load artifact: {e}",
                load_time_ms = self._elapsed(start_time),
            )

        # ── Step 2: Load model weights ────────────────────────────────────────
        try:
            state_dict = torch.load(model_path, map_location=device)
            model      = model_class()
            model.load_state_dict(state_dict)
            model.eval()
        except Exception as e:
            return LoadResult(
                allowed  = False,
                reason   = f"Could not load model file: {e}",
                artifact = artifact,
                load_time_ms = self._elapsed(start_time),
            )

        # ── Step 3: Cryptographic verification ───────────────────────────────
        is_valid, reason, details = self.signer.verify_model(
            model.state_dict(), artifact
        )

        if not is_valid:
            if self.ledger:
                self.ledger.record_verification(artifact, False, reason)
            return LoadResult(
                allowed       = False,
                reason        = reason,
                artifact      = artifact,
                verification  = details,
                load_time_ms  = self._elapsed(start_time),
            )

        # ── Step 4: Policy check ──────────────────────────────────────────────
        allowed, violations = self.policy_engine.evaluate(artifact, self.ledger)
        policy_report       = self.policy_engine.violations_report(violations)

        if not allowed:
            reasons = "; ".join(v.reason for v in violations if v.fatal)
            if self.ledger:
                self.ledger.record_verification(artifact, False, reasons)
            return LoadResult(
                allowed       = False,
                reason        = f"Policy blocked: {reasons}",
                artifact      = artifact,
                verification  = details,
                policy_report = policy_report,
                load_time_ms  = self._elapsed(start_time),
            )

        # ── Step 5: Cache hash for inference-time comparison ──────────────────
        model_id   = artifact["metadata"]["artifact_id"]
        model_hash = artifact["metadata"]["model_hash"]
        hash_cache.set(model_id, model_hash)

        # ── Step 6: Record success in ledger ──────────────────────────────────
        if self.ledger:
            self.ledger.record_verification(artifact, True, "All checks passed")

        return LoadResult(
            allowed       = True,
            reason        = "Model verified and loaded successfully",
            model         = model,
            artifact      = artifact,
            verification  = details,
            policy_report = policy_report,
            load_time_ms  = self._elapsed(start_time),
        )

    def load_from_state_dict(
        self,
        state_dict:    dict,
        artifact:      dict,
        model_class:   type,
    ) -> LoadResult:
        """
        Load from an already-loaded state dict and artifact dict.
        Used by the API where files are uploaded directly.
        """
        start_time = time.time()

        # Cryptographic verification
        is_valid, reason, details = self.signer.verify_model(state_dict, artifact)

        if not is_valid:
            return LoadResult(
                allowed      = False,
                reason       = reason,
                artifact     = artifact,
                verification = details,
                load_time_ms = self._elapsed(start_time),
            )

        # Policy check
        allowed, violations = self.policy_engine.evaluate(artifact, self.ledger)
        policy_report       = self.policy_engine.violations_report(violations)

        if not allowed:
            reasons = "; ".join(v.reason for v in violations if v.fatal)
            return LoadResult(
                allowed       = False,
                reason        = f"Policy blocked: {reasons}",
                artifact      = artifact,
                verification  = details,
                policy_report = policy_report,
                load_time_ms  = self._elapsed(start_time),
            )

        # Build model
        model = model_class()
        model.load_state_dict(state_dict)
        model.eval()

        return LoadResult(
            allowed       = True,
            reason        = "Model verified and loaded successfully",
            model         = model,
            artifact      = artifact,
            verification  = details,
            policy_report = policy_report,
            load_time_ms  = self._elapsed(start_time),
        )

    def wrap_for_inference(
        self,
        load_result:      LoadResult,
        verify_every:     int = 10,
        chunks_per_check: int = 3,
    ) -> InferenceGuard:
        """
        Wrap a successfully loaded model in an InferenceGuard.
        Raises if load_result is not allowed.
        """
        if not load_result.allowed:
            raise RuntimeError("Cannot wrap a blocked model for inference")

        return InferenceGuard(
            model            = load_result.model,
            artifact         = load_result.artifact,
            signer           = self.signer,
            verify_every     = verify_every,
            chunks_per_check = chunks_per_check,
        )

    def _elapsed(self, start: float) -> float:
        return round((time.time() - start) * 1000, 2)