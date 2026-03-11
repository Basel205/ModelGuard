"""
hasher.py — Hashing utilities for ModelGuard

Provides a unified hashing interface using BLAKE3 (primary) with SHA-256 fallback.

Why BLAKE3?
- Faster than SHA-256 (especially on large model files)
- Supports multi-threading natively
- Same security guarantees for our use case
- O(N) but with much smaller constant than SHA-256

Used for:
- Model file fingerprinting
- Chunk hashing in Merkle tree
- Metadata hashing
- Ledger entry hashing
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Union, Optional
import numpy as np

try:
    import blake3
    BLAKE3_AVAILABLE = True
except ImportError:
    BLAKE3_AVAILABLE = False
    print("[hasher] BLAKE3 not available, falling back to SHA-256")


# ── Core hash functions ───────────────────────────────────────────────────────

def hash_bytes(data: bytes, algorithm: str = "blake3") -> str:
    """
    Hash raw bytes. Returns hex string.

    Args:
        data:      raw bytes to hash
        algorithm: 'blake3' or 'sha256'
    """
    if algorithm == "blake3" and BLAKE3_AVAILABLE:
        return blake3.blake3(data).hexdigest()
    return hashlib.sha256(data).hexdigest()


def hash_file(filepath: Union[str, Path], algorithm: str = "blake3") -> str:
    """
    Hash a file in streaming chunks — handles large model files
    without loading everything into memory at once.

    Args:
        filepath:  path to file
        algorithm: 'blake3' or 'sha256'

    Returns hex string of file hash.
    """
    filepath   = Path(filepath)
    chunk_size = 1024 * 1024  # 1MB streaming chunks

    if algorithm == "blake3" and BLAKE3_AVAILABLE:
        hasher = blake3.blake3()
    else:
        hasher = hashlib.sha256()

    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


def hash_string(text: str, algorithm: str = "blake3") -> str:
    """Hash a UTF-8 string."""
    return hash_bytes(text.encode("utf-8"), algorithm)


def hash_dict(data: dict, algorithm: str = "blake3") -> str:
    """
    Hash a dictionary deterministically.
    Sorts keys before hashing to ensure consistency.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hash_string(canonical, algorithm)


def hash_numpy_array(arr: np.ndarray, algorithm: str = "blake3") -> str:
    """Hash a numpy array directly from its raw bytes."""
    return hash_bytes(arr.astype(np.float32).tobytes(), algorithm)


# ── Model-specific hashing ────────────────────────────────────────────────────

def hash_model_weights(state_dict: dict, algorithm: str = "blake3") -> str:
    """
    Produce a single deterministic hash of all model weights.

    Concatenates all weight tensors in sorted key order,
    then hashes the result. This is the model's fingerprint.

    Args:
        state_dict: torch model.state_dict()
        algorithm:  hash algorithm to use

    Returns hex string — this is what gets signed.
    """
    if algorithm == "blake3" and BLAKE3_AVAILABLE:
        hasher = blake3.blake3()
    else:
        hasher = hashlib.sha256()

    # Sort keys for determinism
    for key in sorted(state_dict.keys()):
        tensor = state_dict[key]
        # Hash the key name too — prevents layer-swap attacks
        hasher.update(key.encode("utf-8"))
        hasher.update(tensor.cpu().numpy().astype(np.float32).tobytes())

    return hasher.hexdigest()


def hash_metadata(metadata: dict) -> str:
    """Hash provenance metadata for inclusion in signature."""
    return hash_dict(metadata)


# ── Hash caching ──────────────────────────────────────────────────────────────

class HashCache:
    """
    Cache model hashes to avoid redundant recomputation during inference.

    At inference time we verify integrity periodically.
    Without caching: O(N) every k inferences.
    With caching:    O(1) lookup, O(N) only when model actually changes.
    """

    def __init__(self):
        self._cache: dict = {}
        self._timestamps: dict = {}

    def get(self, model_id: str) -> Optional[str]:
        """Return cached hash or None."""
        return self._cache.get(model_id)

    def set(self, model_id: str, hash_value: str):
        """Store hash with timestamp."""
        self._cache[model_id]      = hash_value
        self._timestamps[model_id] = time.time()

    def invalidate(self, model_id: str):
        """Remove cached hash — forces recomputation on next verify."""
        self._cache.pop(model_id, None)
        self._timestamps.pop(model_id, None)

    def age_seconds(self, model_id: str) -> Optional[float]:
        """How old is the cached hash in seconds."""
        ts = self._timestamps.get(model_id)
        return (time.time() - ts) if ts else None

    def is_stale(self, model_id: str, max_age: float = 300.0) -> bool:
        """Return True if cache entry is older than max_age seconds."""
        age = self.age_seconds(model_id)
        return age is None or age > max_age


# ── Global cache instance ─────────────────────────────────────────────────────

# Shared across the application — import this wherever needed
hash_cache = HashCache()


# ── Utility ───────────────────────────────────────────────────────────────────

def compare_hashes(hash1: str, hash2: str) -> bool:
    """
    Constant-time hash comparison to prevent timing attacks.
    Always use this instead of hash1 == hash2.
    """
    import hmac
    return hmac.compare_digest(hash1, hash2)


def get_algorithm_info() -> dict:
    """Return info about available hash algorithms."""
    return {
        "blake3_available": BLAKE3_AVAILABLE,
        "default_algorithm": "blake3" if BLAKE3_AVAILABLE else "sha256",
        "algorithms": ["blake3", "sha256"],
    }