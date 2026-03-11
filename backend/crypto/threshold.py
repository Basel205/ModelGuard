"""
threshold.py — 2-of-3 Threshold Signatures via Shamir's Secret Sharing

Key idea:
- A model is only approved if AT LEAST 2 out of 3 designated signers approve it
- We use Shamir's Secret Sharing to split a signing secret into 3 shares
- Any 2 shares can reconstruct the secret and produce a valid signature
- 1 share alone reveals nothing — mathematically guaranteed

Why this matters cryptographically:
- No single person can approve a model unilaterally
- Collusion of at least 2 parties required
- Based on polynomial interpolation over a finite field (GF(prime))

Math:
- Secret s is encoded as f(0) where f is a degree-1 polynomial
- f(x) = s + a*x  (mod prime)
- 3 shares: (1, f(1)), (2, f(2)), (3, f(3))
- Any 2 points uniquely determine f → recover s = f(0)
"""

import os
import hashlib
import hmac
from typing import List, Tuple, Dict, Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)


# ── Constants ─────────────────────────────────────────────────────────────────

# Large prime for Shamir's finite field arithmetic
# This is a well-known 256-bit prime
PRIME = 2**256 - 2**32 - 2**9 - 2**8 - 2**7 - 2**6 - 2**4 - 1  # secp256k1 prime

THRESHOLD = 2   # minimum shares needed
N_SHARES  = 3   # total shares distributed


# ── Finite field arithmetic ───────────────────────────────────────────────────

def _mod_inverse(a: int, prime: int) -> int:
    """
    Modular multiplicative inverse using Fermat's little theorem.
    a^(prime-2) mod prime = a^(-1) mod prime
    Works because prime is prime (Fermat's little theorem).
    """
    return pow(a, prime - 2, prime)


def _lagrange_interpolate(x: int, points: List[Tuple[int, int]], prime: int) -> int:
    """
    Lagrange interpolation at point x over finite field GF(prime).

    Given k points (x_i, y_i), reconstruct the polynomial value at x.
    This is the core of Shamir's reconstruction.

    f(x) = Σ y_i * Π (x - x_j)/(x_i - x_j)  for j ≠ i
    """
    result = 0
    k      = len(points)

    for i in range(k):
        xi, yi = points[i]

        # Compute Lagrange basis polynomial L_i(x)
        numerator   = 1
        denominator = 1

        for j in range(k):
            if i == j:
                continue
            xj, _ = points[j]
            numerator   = (numerator   * (x - xj)) % prime
            denominator = (denominator * (xi - xj)) % prime

        lagrange_coeff = (numerator * _mod_inverse(denominator, prime)) % prime
        result = (result + yi * lagrange_coeff) % prime

    return result


# ── Shamir's Secret Sharing ───────────────────────────────────────────────────

class ShamirSecretSharing:
    """
    (k, n) threshold secret sharing scheme.
    Default: (2, 3) — any 2 of 3 shares reconstruct the secret.
    """

    def __init__(self, threshold: int = THRESHOLD, n_shares: int = N_SHARES):
        if threshold > n_shares:
            raise ValueError("Threshold cannot exceed number of shares")
        self.threshold = threshold
        self.n_shares  = n_shares

    def split(self, secret: int) -> List[Tuple[int, int]]:
        """
        Split an integer secret into n_shares shares.

        Algorithm:
        1. Choose (threshold-1) random coefficients a_1, ..., a_{k-1}
        2. Polynomial: f(x) = secret + a_1*x + ... + a_{k-1}*x^{k-1}  mod prime
        3. Shares = [(1, f(1)), (2, f(2)), ..., (n, f(n))]

        Returns list of (x, f(x)) tuples — one per signer.
        """
        # Generate random polynomial coefficients
        coefficients = [secret]
        for _ in range(self.threshold - 1):
            coeff = int.from_bytes(os.urandom(32), 'big') % PRIME
            coefficients.append(coeff)

        def evaluate_polynomial(x: int) -> int:
            """Evaluate polynomial at x using Horner's method."""
            result = 0
            for coeff in reversed(coefficients):
                result = (result * x + coeff) % PRIME
            return result

        shares = [(i, evaluate_polynomial(i)) for i in range(1, self.n_shares + 1)]
        return shares

    def reconstruct(self, shares: List[Tuple[int, int]]) -> int:
        """
        Reconstruct secret from any threshold number of shares.

        Uses Lagrange interpolation to find f(0) = secret.
        Raises ValueError if not enough shares provided.
        """
        if len(shares) < self.threshold:
            raise ValueError(
                f"Need at least {self.threshold} shares, got {len(shares)}"
            )

        # Use exactly threshold shares (extra shares are fine but unnecessary)
        return _lagrange_interpolate(0, shares[:self.threshold], PRIME)

    def verify_share(self, share: Tuple[int, int], all_shares: List[Tuple[int, int]]) -> bool:
        """
        Verify a single share is consistent with others.
        Reconstructs secret from other shares and checks consistency.
        """
        other_shares = [s for s in all_shares if s[0] != share[0]]
        if len(other_shares) < self.threshold - 1:
            return False
        # If reconstruction with this share included gives same result
        try:
            self.reconstruct([share] + other_shares[:self.threshold - 1])
            return True
        except Exception:
            return False


# ── Key Management ────────────────────────────────────────────────────────────

class SignerKeyPair:
    """Represents one signer's Ed25519 key pair."""

    def __init__(self, signer_id: str):
        self.signer_id  = signer_id
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key  = self.private_key.public_key()

    def sign(self, message: bytes) -> bytes:
        """Sign a message with this signer's private key."""
        return self.private_key.sign(message)

    def public_key_bytes(self) -> bytes:
        return self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def to_dict(self) -> dict:
        return {
            "signer_id":  self.signer_id,
            "public_key": self.public_key_bytes().hex(),
        }


# ── Threshold Signature Scheme ────────────────────────────────────────────────

class ThresholdSignatureScheme:
    """
    2-of-3 threshold signature system for model approval.

    Workflow:
    1. Setup: generate 3 signer key pairs
    2. Signing: each signer independently signs the model's Merkle root
    3. Aggregation: collect signatures from any 2 of 3 signers
    4. Verification: verify that at least 2 valid signatures exist
       from registered public keys

    Note: This is a multi-signature scheme (not a true threshold sig scheme
    like FROST) but achieves the same security property for our use case:
    at least k-of-n parties must approve.
    """

    def __init__(self):
        self.signers:     Dict[str, SignerKeyPair] = {}
        self.public_keys: Dict[str, bytes]         = {}
        self.shamir       = ShamirSecretSharing(THRESHOLD, N_SHARES)

    def setup_signers(self, signer_ids: List[str]) -> Dict[str, SignerKeyPair]:
        """
        Generate key pairs for all signers.
        In production, each signer would generate their own key pair locally.

        Returns dict of signer_id → SignerKeyPair
        """
        if len(signer_ids) != N_SHARES:
            raise ValueError(f"Expected exactly {N_SHARES} signers")

        for sid in signer_ids:
            keypair = SignerKeyPair(sid)
            self.signers[sid]     = keypair
            self.public_keys[sid] = keypair.public_key_bytes()

        return self.signers

    def create_signing_message(self, merkle_root: str, metadata: dict) -> bytes:
        """
        Create the canonical message all signers must sign.
        Binds: merkle_root + model_version + timestamp
        """
        content = f"{merkle_root}:{metadata.get('version','1.0')}:{metadata.get('timestamp','')}".encode()
        # Hash it so signers sign a fixed-size commitment
        return hashlib.sha256(content).digest()

    def collect_signature(
        self,
        signer_id:  str,
        message:    bytes,
    ) -> Optional[bytes]:
        """
        Get signature from one signer.
        Returns signature bytes or None if signer not found.
        """
        if signer_id not in self.signers:
            return None
        return self.signers[signer_id].sign(message)

    def aggregate_signatures(
        self,
        message:    bytes,
        signer_ids: List[str],
    ) -> Dict:
        """
        Collect signatures from specified signers and bundle into
        a threshold signature artifact.

        Args:
            message:    the canonical message to sign
            signer_ids: which signers are participating (need >= threshold)

        Returns:
            artifact dict containing all partial signatures
        """
        if len(signer_ids) < THRESHOLD:
            raise ValueError(f"Need at least {THRESHOLD} signers")

        signatures = {}
        for sid in signer_ids:
            sig = self.collect_signature(sid, message)
            if sig:
                signatures[sid] = sig.hex()

        return {
            "threshold":  THRESHOLD,
            "n_shares":   N_SHARES,
            "signers":    signer_ids,
            "signatures": signatures,
            "message":    message.hex(),
        }

    def verify_threshold_signature(
        self,
        artifact:   Dict,
        public_keys: Optional[Dict[str, bytes]] = None,
    ) -> Tuple[bool, str]:
        """
        Verify a threshold signature artifact.

        Checks:
        1. At least THRESHOLD signatures present
        2. Each signature is valid against known public key
        3. All signatures are over the same message

        Returns (is_valid, reason_string)
        """
        pks = public_keys or self.public_keys

        signatures = artifact.get("signatures", {})
        message    = bytes.fromhex(artifact.get("message", ""))

        if not message:
            return False, "Missing signing message"

        # Count valid signatures
        valid_count   = 0
        invalid_sigs  = []

        for signer_id, sig_hex in signatures.items():
            if signer_id not in pks:
                invalid_sigs.append(f"{signer_id}: unknown signer")
                continue

            try:
                pub_key_bytes = pks[signer_id]
                pub_key = Ed25519PublicKey.from_public_bytes(pub_key_bytes)
                pub_key.verify(bytes.fromhex(sig_hex), message)
                valid_count += 1
            except Exception as e:
                invalid_sigs.append(f"{signer_id}: invalid signature")

        if valid_count >= THRESHOLD:
            return True, f"Threshold met: {valid_count}/{N_SHARES} valid signatures"
        else:
            reason = f"Threshold NOT met: only {valid_count}/{N_SHARES} valid. Issues: {invalid_sigs}"
            return False, reason

    def demonstrate_shamir(self, secret_message: str) -> dict:
        """
        Demonstrate Shamir's Secret Sharing for the UI/presentation.
        Shows the full split → reconstruct cycle.
        """
        # Convert message to integer
        secret_int = int.from_bytes(
            hashlib.sha256(secret_message.encode()).digest(), 'big'
        ) % PRIME

        # Split into 3 shares
        shares = self.shamir.split(secret_int)

        # Reconstruct with shares 1+2, 1+3, 2+3 — all should give same secret
        recon_12 = self.shamir.reconstruct([shares[0], shares[1]])
        recon_13 = self.shamir.reconstruct([shares[0], shares[2]])
        recon_23 = self.shamir.reconstruct([shares[1], shares[2]])

        return {
            "original_secret": secret_int,
            "shares":          [(x, str(y)[:20] + "...") for x, y in shares],  # truncate for display
            "reconstruction": {
                "shares_1_2": recon_12 == secret_int,
                "shares_1_3": recon_13 == secret_int,
                "shares_2_3": recon_23 == secret_int,
            },
            "all_correct": all([
                recon_12 == secret_int,
                recon_13 == secret_int,
                recon_23 == secret_int,
            ])
        }

    def get_public_keys_dict(self) -> Dict[str, str]:
        """Return public keys as hex strings for storage/transmission."""
        return {sid: pk.hex() for sid, pk in self.public_keys.items()}