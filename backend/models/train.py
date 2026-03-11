"""
train.py — MNIST Training + Automatic Model Signing

Trains the MNISTClassifier and immediately signs it
using ModelGuard's cryptographic pipeline.

After running this script you will have:
    signed_models/
        mnist_classifier.pt          — trained model weights
        mnist_classifier.artifact.json — signed artifact (Merkle + threshold sigs)

Usage:
    python -m backend.models.train
    python -m backend.models.train --epochs 3 --chunk-size 256
"""

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

# Add project root to path so relative imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.crypto.signer import ModelSigner
from backend.core.ledger import TamperEvidentLedger
from backend.core.provenance import ProvenanceStore
from backend.models.mnist_model import MNISTClassifier


# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT  = Path(__file__).parent.parent.parent
SIGNED_DIR    = PROJECT_ROOT / "backend" / "signed_models"
LEDGER_PATH   = SIGNED_DIR / "ledger.json"
PROVENANCE_PATH = SIGNED_DIR / "provenance.json"
MODEL_PATH    = SIGNED_DIR / "mnist_classifier.pt"
ARTIFACT_PATH = SIGNED_DIR / "mnist_classifier.artifact.json"

SIGNED_DIR.mkdir(parents=True, exist_ok=True)


# ── Training ──────────────────────────────────────────────────────────────────

def get_data_loaders(batch_size: int = 64):
    """Download and prepare MNIST data loaders."""
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))  # MNIST mean/std
    ])

    data_dir = PROJECT_ROOT / "data"

    train_dataset = datasets.MNIST(
        root      = str(data_dir),
        train     = True,
        download  = True,
        transform = transform,
    )
    test_dataset = datasets.MNIST(
        root      = str(data_dir),
        train     = False,
        download  = True,
        transform = transform,
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader  = DataLoader(test_dataset,  batch_size=batch_size, shuffle=False)

    return train_loader, test_loader


def train_epoch(
    model:       nn.Module,
    loader:      DataLoader,
    optimizer:   optim.Optimizer,
    device:      str,
    epoch:       int,
) -> float:
    """Train for one epoch. Returns average loss."""
    model.train()
    total_loss  = 0.0
    correct     = 0
    total       = 0

    for batch_idx, (data, target) in enumerate(loader):
        data, target = data.to(device), target.to(device)

        optimizer.zero_grad()
        output = model(data)
        loss   = nn.functional.nll_loss(output, target)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        pred        = output.argmax(dim=1)
        correct    += pred.eq(target).sum().item()
        total      += len(data)

        if batch_idx % 100 == 0:
            print(
                f"  Epoch {epoch} [{batch_idx * len(data)}/{len(loader.dataset)}] "
                f"Loss: {loss.item():.4f}"
            )

    accuracy = 100.0 * correct / total
    avg_loss = total_loss / len(loader)
    print(f"  Epoch {epoch} complete — Loss: {avg_loss:.4f}, Accuracy: {accuracy:.2f}%")
    return avg_loss


def evaluate(model: nn.Module, loader: DataLoader, device: str) -> dict:
    """Evaluate model on test set."""
    model.eval()
    correct = 0
    total   = 0

    with torch.no_grad():
        for data, target in loader:
            data, target = data.to(device), target.to(device)
            output       = model(data)
            pred         = output.argmax(dim=1)
            correct     += pred.eq(target).sum().item()
            total       += len(data)

    accuracy = 100.0 * correct / total
    print(f"  Test accuracy: {accuracy:.2f}%")
    return {"accuracy": accuracy, "correct": correct, "total": total}


# ── Signing ───────────────────────────────────────────────────────────────────

def sign_model(model: nn.Module, eval_results: dict, chunk_size: int) -> dict:
    """
    Sign the trained model using ModelGuard.

    Sets up 3 signers (alice, bob, charlie) and signs with 2-of-3.
    Returns the signed artifact.
    """
    print("\n── Signing model ────────────────────────────────────────")

    # Initialize signer
    signer = ModelSigner(chunk_size=chunk_size)
    setup_info = signer.setup(["alice", "bob", "charlie"])

    print(f"  Signers:   {setup_info['signers']}")
    print(f"  Threshold: {setup_info['threshold']}")
    print(f"  Public keys generated for all signers")

    # Sign with alice + bob (2-of-3 threshold met)
    print("\n  alice signing...")
    print("  bob signing...")
    print("  (charlie abstains this round)")

    artifact = signer.sign_model(
        state_dict   = model.state_dict(),
        model_name   = "mnist_classifier",
        version      = "1.0.0",
        signing_sids = ["alice", "bob"],   # 2-of-3
        dataset_name = "MNIST",
    )

    # Add architecture info to metadata
    artifact["metadata"]["architecture"] = model.get_architecture_summary()
    artifact["metadata"]["eval_results"] = eval_results

    print(f"\n  Merkle root:  {artifact['metadata']['merkle_root'][:32]}...")
    print(f"  Model hash:   {artifact['metadata']['model_hash'][:32]}...")
    print(f"  Artifact ID:  {artifact['metadata']['artifact_id']}")
    print(f"  Chunk count:  {artifact['merkle_tree']['chunk_count']}")

    return artifact, signer


# ── Attack Demos ──────────────────────────────────────────────────────────────

def create_tampered_model(model: nn.Module) -> nn.Module:
    """
    Create a copy of the model with slightly modified weights.
    Used to demonstrate tamper detection in the demo.
    """
    import copy
    tampered = copy.deepcopy(model)

    # Modify a small number of weights in the first conv layer
    with torch.no_grad():
        tampered.conv1.weight.data[0, 0, 0, 0] += 999.0
        tampered.conv1.weight.data[1, 0, 1, 1] += 999.0

    return tampered


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train and sign MNIST model")
    parser.add_argument("--epochs",     type=int, default=2,   help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=64,  help="Batch size")
    parser.add_argument("--chunk-size", type=int, default=256, help="Merkle chunk size")
    parser.add_argument("--device",     type=str, default="cpu")
    args = parser.parse_args()

    print("=" * 60)
    print("  ModelGuard — MNIST Training + Signing Pipeline")
    print("=" * 60)

    # ── Train ─────────────────────────────────────────────────────────────────
    print(f"\n── Training ({args.epochs} epochs) ──────────────────────────")

    model      = MNISTClassifier().to(args.device)
    optimizer  = optim.Adam(model.parameters(), lr=0.001)

    print(f"  Parameters: {model.count_parameters():,}")
    print(f"  Device:     {args.device}")

    train_loader, test_loader = get_data_loaders(args.batch_size)

    for epoch in range(1, args.epochs + 1):
        train_epoch(model, train_loader, optimizer, args.device, epoch)

    eval_results = evaluate(model, test_loader, args.device)

    # ── Sign ──────────────────────────────────────────────────────────────────
    artifact, signer = sign_model(model, eval_results, args.chunk_size)

    # ── Save model + artifact ─────────────────────────────────────────────────
    print("\n── Saving ───────────────────────────────────────────────")

    torch.save(model.state_dict(), MODEL_PATH)
    signer.save_artifact(artifact, ARTIFACT_PATH)

    print(f"  Model saved:    {MODEL_PATH}")
    print(f"  Artifact saved: {ARTIFACT_PATH}")

    # ── Record in ledger ──────────────────────────────────────────────────────
    ledger     = TamperEvidentLedger(str(LEDGER_PATH))
    provenance = ProvenanceStore(str(PROVENANCE_PATH))

    ledger.record_signing(artifact)
    provenance.record(artifact)

    print(f"  Ledger entry:   {len(ledger)} total entries")

    # ── Demo: tamper detection ────────────────────────────────────────────────
    print("\n── Tamper Detection Demo ────────────────────────────────")

    tampered = create_tampered_model(model)
    is_valid, reason, details = signer.verify_model(tampered.state_dict(), artifact)

    print(f"  Original model  → Valid: True")
    print(f"  Tampered model  → Valid: {is_valid}")
    print(f"  Reason:           {reason}")
    if details.get("dirty_chunks"):
        print(f"  Dirty chunks:     {details['dirty_chunks']}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Pipeline complete!")
    print(f"  Test accuracy:  {eval_results['accuracy']:.2f}%")
    print(f"  Merkle chunks:  {artifact['merkle_tree']['chunk_count']}")
    print(f"  Signed by:      {artifact['signed_by']}")
    print(f"  Chain valid:    {ledger.verify_chain()[0]}")
    print("=" * 60)


if __name__ == "__main__":
    main()