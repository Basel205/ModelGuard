# ModelGuard

*Cryptographically Enforced AI Model Integrity System*

ModelGuard is a security and observability framework designed to ensure the integrity of trained machine learning models across their lifecycle. It transforms the "black box" of model distribution into a transparent, mathematically verifiable system.

## 🚀 Key Features

### 1. Observable Verification Pipeline
Instead of a simple "green checkmark," ModelGuard provides a **4-stage observable verification pipeline** that executes in real-time, displaying cryptographically proven state changes and actual computation timings:
1. **BLAKE3 Hash Check**: Fast cryptographical hash comparisons.
2. **Merkle Root Verification**: Validates the structure across thousands of chunks.
3. **Threshold Signatures (2-of-3)**: Verifies that multiple trusted parties (e.g., Alice and Bob) have signed the model.
4. **Policy Engine**: Checks deployment conditions and security configurations.

### 2. Dynamic Merkle Tree with O(log N) Proofs
ModelGuard splits models into chunk arrays, constructing a binary Merkle Tree over these chunks.
- Enables **O(log N) verification** of any individual part of the model.
- **Diff Visualization**: Simulate attacks (weight modifications, downgrades) and visually identify which specific chunks in the tree were tampered with.

### 3. Decentralized Model Registry
A registry interface derived entirely from a **hash-chained ledger** — no centralized database is required. Tracks the verifiable history of every model variation, retaining a tamper-proof event timeline for verifications, rejections, and simulated attacks.

### 4. Shamir's Secret Sharing (SSS)
Includes a functional demonstration of cryptographic secret sharing techniques, distributing decryption keys/trust among multiple parties.

## 💻 Tech Stack
- **Backend:** Python + FastAPI + PyCryptodome (Ed25519, BLAKE3, Merkle Trees)
- **Frontend:** React + Vite + Vanilla CSS (Dynamic Web Animations)

## 🛠️ Getting Started

### 1. Start the Backend API
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate # Unix/Mac
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --port 8000
```

### 2. Start the Frontend Application
```bash
cd frontend
npm install
npm run dev
```

Navigate to `http://localhost:5173/` to view the ModelGuard interactive dashboard.

## 🔐 Architecture
- `backend/crypto/` houses all core cryptographic logic (`signer.py`, `merkle.py`, `sss.py`).
- `backend/core/` houses the state and `ledger.py` for block tracking.
- `backend/api/main.py` presents the endpoints driving the UI visualizations.
- `frontend/src/pages/` implements the various dashboard routes (`Verification`, `Merkle Tree`, `Attack Sim`, `Registry`, etc).

## 🛡️ Built For Trust
ModelGuard is built to satisfy rigorous academic and enterprise tracking requirements, allowing multiple stakeholders to guarantee that an AI model executed in production is exactly the model that was distributed and signed.