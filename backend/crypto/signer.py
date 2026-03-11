"""
signer.py — Model signing and verification

This is the main entry point for cryptographic operations.
Ties together: Merkle tree + Threshold signatures + Hashing

Signing flow:
    trained model → hash weights → build merkle tree
    → create metadata → threshold sign → save artifact

Verification flow:
    load artifact → recompute hashes → verify merkle root
    → verify threshold signatures → check policy → allow/block
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np

from .merkle import MerkleTree, build_model_merkle_tree
from .threshold import ThresholdSignatureScheme, THRESHOLD, N_SHARES
from .hasher import hash_model_weights, hash_dict, hash_bytes, compare_hashes


# ── Artifact structure ────────────────────────────────────────────────────────

def create_provenance_metadata(
    model_name:    str,
    version:       str,
    model_hash:    str,
    merkle_root:   str,
    dataset_name:  Optional[str] = None,
    extra:         Optional[dict] = None,
) -> dict:
    """
    Create signed provenance metadata record.

    This gets included in the signed artifact and
    binds the model to its training context.
    """
    metadata = {
        "artifact_id":  str(uuid.uuid4()),
        "model_name":   model_name,
        "version":      version,
        "model_hash":   model_hash,
        "merkle_root":  merkle_root,
        "timestamp":    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_name": dataset_name or "unknown",
        "threshold":    f"{THRESHOLD}-of-{N_SHARES}",
    }
    if extra:
        metadata.update(extra)
    return metadata


# ── Main Signer class ─────────────────────────────────────────────────────────

class ModelSigner:
    """
    Main class for signing and verifying AI models.

    Usage:
        signer = ModelSigner()
        signer.setup(["alice", "bob", "charlie"])

        # Sign a model
        artifact = signer.sign_model(state_dict, "mnist_classifier", "1.0")

        # Verify later
        is_valid, reason = signer.verify_model(state_dict, artifact)
    """

    def __init__(self, chunk_size: int = 256):
        self.chunk_size = chunk_size
        self.tss        = ThresholdSignatureScheme()
        self.signers    = {}
        self._is_setup  = False

    def setup(self, signer_ids: List[str]) -> Dict:
        """
        Initialize the signing system with n signers.
        Returns public keys for all signers.
        """
        self.signers   = self.tss.setup_signers(signer_ids)
        self._is_setup = True

        return {
            "signers":     signer_ids,
            "public_keys": self.tss.get_public_keys_dict(),
            "threshold":   f"{THRESHOLD}-of-{N_SHARES}",
        }

    def sign_model(
        self,
        state_dict:   dict,
        model_name:   str,
        version:      str,
        signing_sids: Optional[List[str]] = None,
        dataset_name: Optional[str] = None,
    ) -> dict:
        """
        Fully sign a model — produces a signed artifact.

        Steps:
        1. Hash all model weights → model_hash
        2. Build Merkle tree over weight chunks → merkle_root
        3. Create provenance metadata
        4. Threshold sign (merkle_root + metadata)
        5. Bundle into artifact

        Args:
            state_dict:   torch model.state_dict()
            model_name:   human-readable name
            version:      semantic version string e.g. "1.0.0"
            signing_sids: which signers participate (default: all)
            dataset_name: optional dataset label for provenance

        Returns:
            Signed artifact dict — save this as JSON alongside model
        """
        if not self._is_setup:
            raise RuntimeError("Call setup() before signing")

        signing_sids = signing_sids or list(self.signers.keys())

        # ── Step 1: Hash weights ──────────────────────────────────────────────
        model_hash = hash_model_weights(state_dict)

        # ── Step 2: Build Merkle tree ─────────────────────────────────────────
        merkle_tree = build_model_merkle_tree(state_dict, self.chunk_size)
        merkle_root = merkle_tree.root_hex

        # ── Step 3: Create metadata ───────────────────────────────────────────
        metadata = create_provenance_metadata(
            model_name   = model_name,
            version      = version,
            model_hash   = model_hash,
            merkle_root  = merkle_root,
            dataset_name = dataset_name,
        )

        # ── Step 4: Threshold sign ────────────────────────────────────────────
        message           = self.tss.create_signing_message(merkle_root, metadata)
        threshold_artifact = self.tss.aggregate_signatures(message, signing_sids)

        # ── Step 5: Bundle artifact ───────────────────────────────────────────
        artifact = {
            "metadata":            metadata,
            "merkle_tree":         merkle_tree.to_dict(),
            "threshold_signature": threshold_artifact,
            "public_keys":         self.tss.get_public_keys_dict(),
            "signed_by":           signing_sids,
        }

        return artifact

    def verify_model(
        self,
        state_dict: dict,
        artifact:   dict,
    ) -> Tuple[bool, str, dict]:
        """
        Full cryptographic verification of a model.

        Steps:
        1. Recompute model hash → compare with artifact
        2. Rebuild Merkle tree → compare root
        3. Verify threshold signatures
        4. Return verdict

        Returns:
            (is_valid, reason, details_dict)
        """
        details = {
            "hash_valid":      False,
            "merkle_valid":    False,
            "threshold_valid": False,
            "dirty_chunks":    [],
        }

        # ── Step 1: Verify model hash ─────────────────────────────────────────
        expected_hash = artifact["metadata"]["model_hash"]
        actual_hash   = hash_model_weights(state_dict)

        if not compare_hashes(actual_hash, expected_hash):
            return False, "Model hash mismatch — weights have been modified", details

        details["hash_valid"] = True

        # ── Step 2: Verify Merkle tree ────────────────────────────────────────
        new_tree    = build_model_merkle_tree(state_dict, self.chunk_size)
        stored_root = artifact["merkle_tree"]["root"]

        if not compare_hashes(new_tree.root_hex, stored_root):
            # Find exactly which chunks changed
            stored_leaves = [
                bytes.fromhex(h)
                for h in artifact["merkle_tree"]["leaf_hashes"]
            ]
            dirty = [
                i for i, (old, new) in enumerate(
                    zip(stored_leaves, new_tree.leaf_hashes)
                )
                if old != new
            ]
            details["dirty_chunks"] = dirty
            return (
                False,
                f"Merkle root mismatch — {len(dirty)} chunk(s) tampered: {dirty}",
                details,
            )

        details["merkle_valid"] = True

        # ── Step 3: Verify threshold signatures ───────────────────────────────
        public_keys = {
            sid: bytes.fromhex(pk)
            for sid, pk in artifact["public_keys"].items()
        }
        is_valid, reason = self.tss.verify_threshold_signature(
            artifact["threshold_signature"],
            public_keys,
        )

        if not is_valid:
            return False, f"Threshold signature invalid: {reason}", details

        details["threshold_valid"] = True

        return True, "Model verified successfully — all checks passed", details

    def verify_chunk_only(
        self,
        state_dict:   dict,
        artifact:     dict,
        chunk_index:  int,
    ) -> Tuple[bool, str]:
        """
        Lightweight O(log N) verification of a single chunk.
        Used for periodic inference-time checks.
        """
        from .merkle import MerkleTree, chunk_weights
        import numpy as np

        # Rebuild just the chunks
        all_weights = np.concatenate([
            v.cpu().numpy().flatten()
            for v in state_dict.values()
            if hasattr(v, 'numpy')
        ])
        chunks = chunk_weights(all_weights, self.chunk_size)

        if chunk_index >= len(chunks):
            return False, f"Chunk index {chunk_index} out of range"

        # Restore stored tree for proof verification
        stored_tree = MerkleTree.from_dict(artifact["merkle_tree"])
        is_valid    = stored_tree.verify_chunk(chunk_index, chunks[chunk_index])

        if is_valid:
            return True, f"Chunk {chunk_index} verified OK"
        return False, f"Chunk {chunk_index} FAILED verification"

    def save_artifact(self, artifact: dict, path: Union[str, Path]):
        """Save signed artifact as JSON."""
        Path(path).write_text(json.dumps(artifact, indent=2))

    def load_artifact(self, path: Union[str, Path]) -> dict:
        """Load signed artifact from JSON file."""
        return json.loads(Path(path).read_text())

