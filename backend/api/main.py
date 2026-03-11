"""
main.py — FastAPI Backend for ModelGuard

Exposes all cryptographic operations as REST endpoints.
The React frontend calls these endpoints.

Endpoints:
    POST /api/sign          — sign a model
    POST /api/verify        — verify a model
    POST /api/attack        — simulate an attack
    GET  /api/ledger        — get ledger entries
    GET  /api/provenance    — get provenance records
    POST /api/shamir-demo   — demonstrate Shamir's Secret Sharing
    GET  /api/status        — system status
"""

import io
import json
import sys
import copy
from pathlib import Path
from typing import Optional

import torch
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.crypto.signer import ModelSigner
from backend.crypto.threshold import ThresholdSignatureScheme
from backend.core.ledger import TamperEvidentLedger
from backend.core.policy import PolicyEngine, PolicyConfig
from backend.core.loader import SecureModelLoader
from backend.core.provenance import ProvenanceStore
from backend.models.mnist_model import MNISTClassifier


# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT    = Path(__file__).parent.parent.parent
SIGNED_DIR      = PROJECT_ROOT / "backend" / "signed_models"
LEDGER_PATH     = SIGNED_DIR / "ledger.json"
PROVENANCE_PATH = SIGNED_DIR / "provenance.json"
MODEL_PATH      = SIGNED_DIR / "mnist_classifier.pt"
ARTIFACT_PATH   = SIGNED_DIR / "mnist_classifier.artifact.json"


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "ModelGuard API",
    description = "Cryptographically Enforced AI Model Integrity System",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:5173", "http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ── Global state ──────────────────────────────────────────────────────────────
# Initialized once at startup, reused across requests

_signer    : Optional[ModelSigner]          = None
_loader    : Optional[SecureModelLoader]    = None
_ledger    : Optional[TamperEvidentLedger]  = None
_provenance: Optional[ProvenanceStore]      = None
_artifact  : Optional[dict]                 = None
_model     : Optional[torch.nn.Module]      = None


def get_signer() -> ModelSigner:
    global _signer
    if _signer is None:
        _signer = ModelSigner()
        _signer.setup(["alice", "bob", "charlie"])
    return _signer


def get_ledger() -> TamperEvidentLedger:
    global _ledger
    if _ledger is None:
        _ledger = TamperEvidentLedger(str(LEDGER_PATH))
    return _ledger


def get_provenance() -> ProvenanceStore:
    global _provenance
    if _provenance is None:
        _provenance = ProvenanceStore(str(PROVENANCE_PATH))
    return _provenance


def get_loader() -> SecureModelLoader:
    global _loader
    if _loader is None:
        policy = PolicyEngine(PolicyConfig(
            require_signed  = True,
            minimum_signers = 2,
        ))
        _loader = SecureModelLoader(get_signer(), policy, get_ledger())
    return _loader


def get_artifact() -> dict:
    global _artifact
    if _artifact is None:
        if not ARTIFACT_PATH.exists():
            raise HTTPException(
                status_code = 404,
                detail      = "No signed artifact found. Run train.py first."
            )
        _artifact = get_signer().load_artifact(str(ARTIFACT_PATH))
    return _artifact


def get_model() -> torch.nn.Module:
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            raise HTTPException(
                status_code = 404,
                detail      = "No model found. Run train.py first."
            )
        model = MNISTClassifier()
        state_dict = torch.load(str(MODEL_PATH), map_location="cpu")
        model.load_state_dict(state_dict)
        model.eval()
        _model = model
    return _model


# ── Request / Response models ─────────────────────────────────────────────────

class SignRequest(BaseModel):
    model_name:   str         = "mnist_classifier"
    version:      str         = "1.0.0"
    signing_sids: list[str]   = ["alice", "bob"]
    dataset_name: str         = "MNIST"


class AttackRequest(BaseModel):
    attack_type: str   # "modify_weights", "replace_model", "unsigned", "downgrade"
    intensity:   float = 1.0   # how severe the attack is (1.0 = default)


class ShamirDemoRequest(BaseModel):
    secret_message: str = "ModelGuard secret"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    """System status and overview."""
    ledger        = get_ledger()
    chain_valid, chain_reason, _ = ledger.verify_chain()
    artifact_exists = ARTIFACT_PATH.exists()
    model_exists    = MODEL_PATH.exists()

    return {
        "status":          "online",
        "model_trained":   model_exists,
        "model_signed":    artifact_exists,
        "ledger_entries":  len(ledger),
        "chain_valid":     chain_valid,
        "chain_reason":    chain_reason,
        "signed_dir":      str(SIGNED_DIR),
    }


@app.post("/api/sign")
def sign_model(req: SignRequest):
    """
    Sign the trained MNIST model.
    Returns the full signed artifact including Merkle tree and threshold sigs.
    """
    global _artifact

    if not MODEL_PATH.exists():
        raise HTTPException(status_code=404, detail="Model not found. Run train.py first.")

    signer     = get_signer()
    state_dict = torch.load(str(MODEL_PATH), map_location="cpu")

    artifact = signer.sign_model(
        state_dict   = state_dict,
        model_name   = req.model_name,
        version      = req.version,
        signing_sids = req.signing_sids,
        dataset_name = req.dataset_name,
    )

    # Save artifact
    signer.save_artifact(artifact, str(ARTIFACT_PATH))
    _artifact = artifact

    # Record in ledger and provenance
    ledger     = get_ledger()
    provenance = get_provenance()
    ledger.record_signing(artifact)
    provenance.record(artifact)

    return {
        "success":      True,
        "artifact_id":  artifact["metadata"]["artifact_id"],
        "model_hash":   artifact["metadata"]["model_hash"],
        "merkle_root":  artifact["metadata"]["merkle_root"],
        "chunk_count":  artifact["merkle_tree"]["chunk_count"],
        "signed_by":    artifact["signed_by"],
        "threshold":    artifact["metadata"]["threshold"],
        "timestamp":    artifact["metadata"]["timestamp"],
        "leaf_hashes":  artifact["merkle_tree"]["leaf_hashes"][:20],  # first 20 for UI
    }


@app.get("/api/verify")
def verify_model():
    """
    Verify the currently loaded model against its signed artifact.
    Returns detailed verification results for each check.
    """
    signer   = get_signer()
    artifact = get_artifact()
    model    = get_model()

    is_valid, reason, details = signer.verify_model(
        model.state_dict(), artifact
    )

    ledger = get_ledger()
    ledger.record_verification(artifact, is_valid, reason)

    return {
        "valid":           is_valid,
        "reason":          reason,
        "hash_valid":      details.get("hash_valid",      False),
        "merkle_valid":    details.get("merkle_valid",    False),
        "threshold_valid": details.get("threshold_valid", False),
        "dirty_chunks":    details.get("dirty_chunks",    []),
        "artifact_id":     artifact["metadata"]["artifact_id"],
        "model_name":      artifact["metadata"]["model_name"],
        "signed_by":       artifact.get("signed_by", []),
    }


@app.post("/api/attack")
def simulate_attack(req: AttackRequest):
    """
    Simulate various attack scenarios and show ModelGuard detecting them.

    Attack types:
    - modify_weights:  tamper with model weight values
    - replace_model:   swap in a completely different model
    - unsigned:        attempt to load with no artifact
    - downgrade:       replay an old artifact with new model
    """
    signer   = get_signer()
    artifact = get_artifact()
    model    = get_model()

    attack_type = req.attack_type
    result      = {}

    if attack_type == "modify_weights":
        # Modify a few weights and try to verify
        tampered_state = copy.deepcopy(model.state_dict())

        # Number of weights to corrupt scales with intensity
        n_corrupt = max(1, int(req.intensity * 5))
        corrupted_layers = []

        with torch.no_grad():
            keys = list(tampered_state.keys())
            for i in range(min(n_corrupt, len(keys))):
                key = keys[i]
                tampered_state[key].flatten()[0] += 999.0 * req.intensity
                corrupted_layers.append(key)

        is_valid, reason, details = signer.verify_model(tampered_state, artifact)

        result = {
            "attack":          "modify_weights",
            "detected":        not is_valid,
            "reason":          reason,
            "corrupted_layers": corrupted_layers,
            "dirty_chunks":    details.get("dirty_chunks", []),
            "hash_valid":      details.get("hash_valid",   False),
            "merkle_valid":    details.get("merkle_valid", False),
        }

    elif attack_type == "replace_model":
        # Create a freshly initialized (random weights) model
        # and try to verify it against the real artifact
        random_model      = MNISTClassifier()
        random_state_dict = random_model.state_dict()

        is_valid, reason, details = signer.verify_model(random_state_dict, artifact)

        result = {
            "attack":       "replace_model",
            "detected":     not is_valid,
            "reason":       reason,
            "dirty_chunks": details.get("dirty_chunks", []),
            "hash_valid":   details.get("hash_valid",   False),
        }

    elif attack_type == "unsigned":
        # Try to verify with an empty / missing artifact
        fake_artifact = {
            "metadata": {
                "artifact_id": "fake-000",
                "model_name":  "fake",
                "model_hash":  "0" * 64,
                "merkle_root": "0" * 64,
                "version":     "0.0.0",
                "timestamp":   "2000-01-01T00:00:00Z",
                "threshold":   "2-of-3",
                "dataset_name": "unknown",
            },
            "merkle_tree": {
                "root":        "0" * 64,
                "chunk_count": 0,
                "leaf_hashes": [],
            },
            "threshold_signature": {},
            "public_keys":  {},
            "signed_by":    [],
        }

        policy  = PolicyEngine(PolicyConfig(require_signed=True, minimum_signers=2))
        allowed, violations = policy.evaluate(fake_artifact, get_ledger())
        report  = policy.violations_report(violations)

        result = {
            "attack":          "unsigned",
            "detected":        not allowed,
            "reason":          "No valid signatures present",
            "policy_report":   report,
        }

    elif attack_type == "downgrade":
        # Modify artifact version to simulate a downgrade attack
        import copy as copy_mod
        old_artifact = copy_mod.deepcopy(artifact)
        old_artifact["metadata"]["version"] = "0.0.1"

        policy  = PolicyEngine(PolicyConfig(
            require_signed  = True,
            minimum_signers = 2,
            minimum_version = "1.0.0",
        ))
        allowed, violations = policy.evaluate(old_artifact, get_ledger())
        report  = policy.violations_report(violations)

        result = {
            "attack":        "downgrade",
            "detected":      not allowed,
            "reason":        "Version below minimum policy requirement",
            "policy_report": report,
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown attack type: {attack_type}")

    # Record attack attempt in ledger
    ledger = get_ledger()
    ledger.append(
        event_type  = "ATTACK_SIMULATED",
        model_name  = artifact["metadata"]["model_name"],
        model_hash  = artifact["metadata"]["model_hash"],
        merkle_root = artifact["metadata"]["merkle_root"],
        signed_by   = [],
        artifact_id = artifact["metadata"]["artifact_id"],
        extra       = {"attack_type": attack_type, "detected": result.get("detected")},
    )

    return result


@app.get("/api/ledger")
def get_ledger_entries():
    """Return all ledger entries for the audit log UI."""
    ledger = get_ledger()
    chain_valid, chain_reason, broken_at = ledger.verify_chain()

    return {
        "entries":      ledger.to_dict(),
        "total":        len(ledger),
        "chain_valid":  chain_valid,
        "chain_reason": chain_reason,
        "broken_at":    broken_at,
    }


@app.get("/api/provenance")
def get_provenance_records():
    """Return all provenance records."""
    provenance = get_provenance()
    return {
        "records": provenance.get_all(),
        "total":   len(provenance.get_all()),
    }


@app.get("/api/merkle")
def get_merkle_info():
    """
    Return Merkle tree structure for visualization.
    Sends leaf hashes and tree levels to the frontend.
    """
    artifact = get_artifact()
    tree     = artifact["merkle_tree"]

    return {
        "root":        tree["root"],
        "chunk_count": tree["chunk_count"],
        "leaf_hashes": tree["leaf_hashes"],
        "depth":       _compute_tree_depth(tree["chunk_count"]),
    }


@app.post("/api/shamir-demo")
def shamir_demo(req: ShamirDemoRequest):
    """
    Live demonstration of Shamir's Secret Sharing.
    Shows the full split → reconstruct cycle with real numbers.
    Used in the frontend demo panel.
    """
    tss    = ThresholdSignatureScheme()
    tss.setup_signers(["alice", "bob", "charlie"])
    result = tss.demonstrate_shamir(req.secret_message)

    return {
        "secret_message":  req.secret_message,
        "threshold":       "2-of-3",
        "shares_generated": len(result["shares"]),
        "shares":          result["shares"],
        "reconstruction":  result["reconstruction"],
        "all_correct":     result["all_correct"],
        "explanation": {
            "step1": "Secret encoded as f(0) of a degree-1 polynomial",
            "step2": "3 shares generated: (1,f(1)), (2,f(2)), (3,f(3))",
            "step3": "Any 2 shares reconstruct f(0) via Lagrange interpolation",
            "step4": "1 share alone reveals nothing about the secret",
        }
    }


@app.get("/api/chunk-verify/{chunk_index}")
def verify_single_chunk(chunk_index: int):
    """
    Verify a single chunk via O(log N) Merkle proof.
    Used to demonstrate per-chunk verification in the UI.
    """
    signer   = get_signer()
    artifact = get_artifact()
    model    = get_model()

    total_chunks = artifact["merkle_tree"]["chunk_count"]

    if chunk_index >= total_chunks:
        raise HTTPException(
            status_code = 400,
            detail      = f"Chunk index {chunk_index} out of range (max {total_chunks - 1})"
        )

    ok, reason = signer.verify_chunk_only(
        model.state_dict(), artifact, chunk_index
    )

    return {
        "chunk_index":  chunk_index,
        "valid":        ok,
        "reason":       reason,
        "total_chunks": total_chunks,
        "proof_steps":  _compute_tree_depth(total_chunks),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_tree_depth(n: int) -> int:
    """Compute Merkle tree depth for n leaves."""
    import math
    return math.ceil(math.log2(max(n, 2)))