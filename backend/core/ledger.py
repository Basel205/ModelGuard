"""
ledger.py — Tamper-Evident Hash-Chained Ledger

Every model signing event is recorded here.
Entries are chained: each entry contains the hash of the previous entry.
This means you cannot modify or delete history without breaking the chain.

Similar in concept to a blockchain but without consensus — just cryptographic
integrity. Think of it as a append-only audit log.

Chain structure:
    entry_0: { data, prev_hash: "0000...0000" (genesis) }
    entry_1: { data, prev_hash: hash(entry_0) }
    entry_2: { data, prev_hash: hash(entry_1) }
    ...
    entry_N: { data, prev_hash: hash(entry_N-1) }

Tampering with any entry breaks all subsequent hashes.
"""

import json
import time
import hashlib
import uuid
from pathlib import Path
from typing import List, Optional, Tuple


# ── Constants ─────────────────────────────────────────────────────────────────

GENESIS_HASH = "0" * 64  # Previous hash for the very first entry


# ── Entry ─────────────────────────────────────────────────────────────────────

class LedgerEntry:
    """A single entry in the tamper-evident ledger."""

    def __init__(
        self,
        event_type:  str,
        model_name:  str,
        model_hash:  str,
        merkle_root: str,
        signed_by:   List[str],
        artifact_id: str,
        prev_hash:   str,
        extra:       Optional[dict] = None,
    ):
        self.entry_id   = str(uuid.uuid4())
        self.event_type = event_type      # "SIGNED", "VERIFIED", "REJECTED", "REVOKED"
        self.model_name = model_name
        self.model_hash = model_hash
        self.merkle_root = merkle_root
        self.signed_by  = signed_by
        self.artifact_id = artifact_id
        self.prev_hash  = prev_hash
        self.timestamp  = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.extra      = extra or {}

        # Compute this entry's own hash after all fields are set
        self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """
        Hash the full entry content including prev_hash.
        This is what makes the chain tamper-evident.
        """
        content = {
            "entry_id":    self.entry_id,
            "event_type":  self.event_type,
            "model_name":  self.model_name,
            "model_hash":  self.model_hash,
            "merkle_root": self.merkle_root,
            "signed_by":   sorted(self.signed_by),
            "artifact_id": self.artifact_id,
            "prev_hash":   self.prev_hash,
            "timestamp":   self.timestamp,
            "extra":       self.extra,
        }
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "entry_id":    self.entry_id,
            "event_type":  self.event_type,
            "model_name":  self.model_name,
            "model_hash":  self.model_hash,
            "merkle_root": self.merkle_root,
            "signed_by":   self.signed_by,
            "artifact_id": self.artifact_id,
            "prev_hash":   self.prev_hash,
            "timestamp":   self.timestamp,
            "extra":       self.extra,
            "entry_hash":  self.entry_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LedgerEntry":
        """Reconstruct entry from dict. Does NOT recompute hash."""
        instance = object.__new__(cls)
        instance.entry_id    = data["entry_id"]
        instance.event_type  = data["event_type"]
        instance.model_name  = data["model_name"]
        instance.model_hash  = data["model_hash"]
        instance.merkle_root = data["merkle_root"]
        instance.signed_by   = data["signed_by"]
        instance.artifact_id = data["artifact_id"]
        instance.prev_hash   = data["prev_hash"]
        instance.timestamp   = data["timestamp"]
        instance.extra       = data.get("extra", {})
        instance.entry_hash  = data["entry_hash"]
        return instance


# ── Ledger ────────────────────────────────────────────────────────────────────

class TamperEvidentLedger:
    """
    Append-only hash-chained ledger of all model events.

    Key properties:
    - Every entry is linked to the previous via its hash
    - Verifying the chain is O(N) — scan all entries
    - Any tampering breaks the chain at that point
    - Supports persistence to JSON file
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.entries: List[LedgerEntry] = []
        self.storage_path = Path(storage_path) if storage_path else None

        # Load existing ledger from disk if available
        if self.storage_path and self.storage_path.exists():
            self._load()

    # ── Append ────────────────────────────────────────────────────────────────

    def append(
        self,
        event_type:  str,
        model_name:  str,
        model_hash:  str,
        merkle_root: str,
        signed_by:   List[str],
        artifact_id: str,
        extra:       Optional[dict] = None,
    ) -> LedgerEntry:
        """
        Append a new entry to the ledger.
        Automatically chains to the last entry.
        """
        prev_hash = self.entries[-1].entry_hash if self.entries else GENESIS_HASH

        entry = LedgerEntry(
            event_type  = event_type,
            model_name  = model_name,
            model_hash  = model_hash,
            merkle_root = merkle_root,
            signed_by   = signed_by,
            artifact_id = artifact_id,
            prev_hash   = prev_hash,
            extra       = extra,
        )

        self.entries.append(entry)

        # Persist to disk after every append
        if self.storage_path:
            self._save()

        return entry

    def record_signing(self, artifact: dict) -> LedgerEntry:
        """Convenience method — record a model signing event."""
        meta = artifact["metadata"]
        return self.append(
            event_type  = "SIGNED",
            model_name  = meta["model_name"],
            model_hash  = meta["model_hash"],
            merkle_root = meta["merkle_root"],
            signed_by   = artifact["signed_by"],
            artifact_id = meta["artifact_id"],
            extra       = {"version": meta["version"]},
        )

    def record_verification(
        self,
        artifact:  dict,
        success:   bool,
        reason:    str,
    ) -> LedgerEntry:
        """Record a verification attempt (pass or fail)."""
        meta = artifact["metadata"]
        return self.append(
            event_type  = "VERIFIED" if success else "REJECTED",
            model_name  = meta["model_name"],
            model_hash  = meta["model_hash"],
            merkle_root = meta["merkle_root"],
            signed_by   = artifact.get("signed_by", []),
            artifact_id = meta["artifact_id"],
            extra       = {"reason": reason, "success": success},
        )

    def record_revocation(self, artifact: dict, reason: str) -> LedgerEntry:
        """Record a model revocation event."""
        meta = artifact["metadata"]
        return self.append(
            event_type  = "REVOKED",
            model_name  = meta["model_name"],
            model_hash  = meta["model_hash"],
            merkle_root = meta["merkle_root"],
            signed_by   = artifact.get("signed_by", []),
            artifact_id = meta["artifact_id"],
            extra       = {"revocation_reason": reason},
        )

    # ── Verification ──────────────────────────────────────────────────────────

    def verify_chain(self) -> Tuple[bool, str, int]:
        """
        Verify the entire chain integrity.

        Walks every entry and recomputes its hash,
        then checks that prev_hash matches the previous entry.

        Returns:
            (is_valid, reason, first_broken_index)
        """
        if not self.entries:
            return True, "Ledger is empty", -1

        # Verify genesis entry
        first = self.entries[0]
        if first.prev_hash != GENESIS_HASH:
            return False, "Genesis entry has wrong prev_hash", 0

        recomputed = first._compute_hash()
        if recomputed != first.entry_hash:
            return False, "Genesis entry hash is invalid — entry was tampered", 0

        # Verify rest of chain
        for i in range(1, len(self.entries)):
            current  = self.entries[i]
            previous = self.entries[i - 1]

            # Check linkage
            if current.prev_hash != previous.entry_hash:
                return (
                    False,
                    f"Chain broken at entry {i} — prev_hash mismatch",
                    i,
                )

            # Check entry hasn't been modified
            recomputed = current._compute_hash()
            if recomputed != current.entry_hash:
                return (
                    False,
                    f"Entry {i} hash is invalid — entry was tampered",
                    i,
                )

        return True, f"Chain valid — {len(self.entries)} entries verified", -1

    def is_revoked(self, artifact_id: str) -> bool:
        """Check if a specific artifact has been revoked."""
        for entry in self.entries:
            if entry.artifact_id == artifact_id and entry.event_type == "REVOKED":
                return True
        return False

    def get_model_history(self, model_name: str) -> List[dict]:
        """Get all ledger entries for a specific model."""
        return [
            e.to_dict()
            for e in self.entries
            if e.model_name == model_name
        ]

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self):
        """Persist ledger to JSON file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self.entries]
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _load(self):
        """Load ledger from JSON file."""
        data = json.loads(self.storage_path.read_text())
        self.entries = [LedgerEntry.from_dict(d) for d in data]

    def to_dict(self) -> List[dict]:
        """Return all entries as list of dicts — for API responses."""
        return [e.to_dict() for e in self.entries]

    def __len__(self):
        return len(self.entries)
