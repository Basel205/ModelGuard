"""
provenance.py — Provenance Metadata Manager

Handles creation, storage, and retrieval of model provenance records.
Provenance answers: where did this model come from, who approved it,
what data was it trained on, and has it changed since?
"""

import json
import time
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict


@dataclass
class ProvenanceRecord:
    """Full provenance record for a signed model."""
    artifact_id:   str
    model_name:    str
    version:       str
    model_hash:    str
    merkle_root:   str
    dataset_name:  str
    signed_by:     List[str]
    timestamp:     str
    threshold:     str
    notes:         Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_artifact(cls, artifact: dict) -> "ProvenanceRecord":
        """Extract provenance from a signed artifact."""
        meta = artifact["metadata"]
        return cls(
            artifact_id  = meta["artifact_id"],
            model_name   = meta["model_name"],
            version      = meta["version"],
            model_hash   = meta["model_hash"],
            merkle_root  = meta["merkle_root"],
            dataset_name = meta.get("dataset_name", "unknown"),
            signed_by    = artifact.get("signed_by", []),
            timestamp    = meta["timestamp"],
            threshold    = meta.get("threshold", "2-of-3"),
            notes        = meta.get("notes"),
        )


class ProvenanceStore:
    """
    Stores and retrieves provenance records.
    Persists to a JSON file alongside the ledger.
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.records: dict = {}
        self.storage_path  = Path(storage_path) if storage_path else None

        if self.storage_path and self.storage_path.exists():
            self._load()

    def record(self, artifact: dict) -> ProvenanceRecord:
        """Extract and store provenance from a signed artifact."""
        rec = ProvenanceRecord.from_artifact(artifact)
        self.records[rec.artifact_id] = rec.to_dict()
        if self.storage_path:
            self._save()
        return rec

    def get(self, artifact_id: str) -> Optional[dict]:
        return self.records.get(artifact_id)

    def get_all(self) -> List[dict]:
        return list(self.records.values())

    def get_by_model(self, model_name: str) -> List[dict]:
        return [
            r for r in self.records.values()
            if r["model_name"] == model_name
        ]

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(self.records, indent=2))

    def _load(self):
        self.records = json.loads(self.storage_path.read_text())
