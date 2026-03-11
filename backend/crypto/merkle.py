"""
merkle.py — Merkle Tree over AI model weight chunks

Key idea:
- Split model weights into N chunks
- Build a binary Merkle tree over their hashes
- Root hash = cryptographic fingerprint of the entire model
- Verification of any single chunk = O(log N) instead of O(N)

This is the foundation of ModelGuard's efficient tamper detection.
"""

import hashlib
import math
from typing import List, Tuple, Optional
import numpy as np


# ── Hashing primitive ────────────────────────────────────────────────────────

def _hash(data: bytes) -> bytes:
    """SHA-256 hash of raw bytes. Returns 32-byte digest."""
    return hashlib.sha256(data).digest()

def _hash_pair(left: bytes, right: bytes) -> bytes:
    """Hash two child nodes together to produce a parent node."""
    return _hash(left + right)


# ── Chunk utilities ──────────────────────────────────────────────────────────

def chunk_weights(flat_weights: np.ndarray, chunk_size: int = 256) -> List[bytes]:
    """
    Split a flat numpy array of model weights into fixed-size byte chunks.

    Args:
        flat_weights: 1D numpy array of all model parameters concatenated
        chunk_size:   number of float32 values per chunk (default 256)

    Returns:
        List of raw byte strings, one per chunk
    """
    # Convert to float32 for consistency across platforms
    weights_bytes = flat_weights.astype(np.float32).tobytes()
    chunk_bytes   = chunk_size * 4  # 4 bytes per float32

    chunks = [
        weights_bytes[i : i + chunk_bytes]
        for i in range(0, len(weights_bytes), chunk_bytes)
    ]
    return chunks


# ── Merkle Tree ──────────────────────────────────────────────────────────────

class MerkleTree:
    """
    Binary Merkle tree built over model weight chunks.

    Properties:
    - tree[0]         = root hash
    - tree[1], tree[2] = children of root
    - For node i: left child = 2i+1, right child = 2i+2
    - Leaves are stored at the bottom level
    """

    def __init__(self, chunks: List[bytes]):
        if not chunks:
            raise ValueError("Cannot build Merkle tree from empty chunks")

        self.chunk_count = len(chunks)
        self.leaf_hashes: List[bytes] = [_hash(c) for c in chunks]
        self.tree:        List[bytes] = []
        self._build()

    def _build(self):
        """
        Build the full tree bottom-up.
        If odd number of nodes at any level, duplicate the last node (standard practice).
        """
        level = list(self.leaf_hashes)

        # We'll store levels so we can index into them
        levels = [level]

        while len(level) > 1:
            next_level = []
            # Pad to even length
            if len(level) % 2 == 1:
                level.append(level[-1])  # duplicate last node
            for i in range(0, len(level), 2):
                next_level.append(_hash_pair(level[i], level[i + 1]))
            levels.append(next_level)
            level = next_level

        # Root is the last single element
        self.levels   = levels          # levels[0] = leaves, levels[-1] = [root]
        self.root     = levels[-1][0]

    @property
    def root_hex(self) -> str:
        return self.root.hex()

    def get_proof(self, leaf_index: int) -> List[Tuple[str, bytes]]:
        """
        Generate a Merkle proof for chunk at leaf_index.

        Returns list of (side, hash) pairs where side is 'left' or 'right'.
        The verifier uses this to recompute the root from just one leaf.

        Complexity: O(log N)
        """
        if leaf_index < 0 or leaf_index >= self.chunk_count:
            raise IndexError(f"Leaf index {leaf_index} out of range")

        proof = []
        idx   = leaf_index

        for level in self.levels[:-1]:  # all levels except root
            # Pad level if needed (same rule as build)
            padded = level[:]
            if len(padded) % 2 == 1:
                padded.append(padded[-1])

            # Find sibling
            if idx % 2 == 0:
                sibling_idx  = idx + 1
                sibling_side = "right"
            else:
                sibling_idx  = idx - 1
                sibling_side = "left"

            proof.append((sibling_side, padded[sibling_idx]))
            idx //= 2  # move up to parent index

        return proof

    def verify_proof(
        self,
        leaf_hash:  bytes,
        leaf_index: int,
        proof:      List[Tuple[str, bytes]],
        root:       bytes,
    ) -> bool:
        """
        Verify a Merkle proof in O(log N).

        Args:
            leaf_hash:  hash of the chunk being verified
            leaf_index: position in original chunk list
            proof:      list of (side, hash) from get_proof()
            root:       expected root hash

        Returns:
            True if the proof is valid against the given root
        """
        computed = leaf_hash
        idx      = leaf_index

        for side, sibling_hash in proof:
            if side == "right":
                computed = _hash_pair(computed, sibling_hash)
            else:
                computed = _hash_pair(sibling_hash, computed)
            idx //= 2

        return computed == root

    def get_dirty_chunks(self, new_chunks: List[bytes]) -> List[int]:
        """
        Incrementally find which chunks changed between old and new model.
        Only recomputes hashes for leaves — O(N) scan but avoids full re-hash.

        Returns list of changed chunk indices.
        Used for incremental verification at inference time.
        """
        dirty = []
        new_leaf_hashes = [_hash(c) for c in new_chunks]

        for i, (old_h, new_h) in enumerate(zip(self.leaf_hashes, new_leaf_hashes)):
            if old_h != new_h:
                dirty.append(i)

        return dirty

    def verify_chunk(self, chunk_index: int, chunk_data: bytes) -> bool:
        """
        Verify a single chunk against the stored Merkle root.
        This is what gets called at inference time — O(log N).

        Args:
            chunk_index: which chunk to verify
            chunk_data:  raw bytes of the chunk

        Returns:
            True if chunk is unmodified
        """
        leaf_hash = _hash(chunk_data)
        proof     = self.get_proof(chunk_index)
        return self.verify_proof(leaf_hash, chunk_index, proof, self.root)

    def to_dict(self) -> dict:
        """Serialize tree metadata for storage in signed artifact."""
        return {
            "root":        self.root_hex,
            "chunk_count": self.chunk_count,
            "leaf_hashes": [h.hex() for h in self.leaf_hashes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MerkleTree":
        """
        Reconstruct a MerkleTree from serialized dict.
        Used when loading a signed model artifact.
        """
        # Rebuild from leaf hashes directly
        instance = object.__new__(cls)
        instance.chunk_count = data["chunk_count"]
        instance.leaf_hashes = [bytes.fromhex(h) for h in data["leaf_hashes"]]
        instance._build_from_leaves()
        return instance

    def _build_from_leaves(self):
        """Rebuild tree from already-computed leaf hashes."""
        level  = list(self.leaf_hashes)
        levels = [level]

        while len(level) > 1:
            next_level = []
            if len(level) % 2 == 1:
                level.append(level[-1])
            for i in range(0, len(level), 2):
                next_level.append(_hash_pair(level[i], level[i + 1]))
            levels.append(next_level)
            level = next_level

        self.levels = levels
        self.root   = levels[-1][0]


# ── Standalone helper ─────────────────────────────────────────────────────────

def build_model_merkle_tree(model_weights: dict, chunk_size: int = 256) -> MerkleTree:
    """
    Build a Merkle tree directly from a PyTorch state_dict.

    Args:
        model_weights: torch model.state_dict()
        chunk_size:    weights per chunk

    Returns:
        MerkleTree instance
    """
    # Flatten all weight tensors into one numpy array
    all_weights = np.concatenate([
        v.cpu().numpy().flatten()
        for v in model_weights.values()
        if hasattr(v, 'numpy')
    ])

    chunks = chunk_weights(all_weights, chunk_size)
    return MerkleTree(chunks)
