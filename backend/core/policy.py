"""
policy.py — Policy Engine for ModelGuard

Defines and enforces rules about which models are allowed to execute.
Think of it as a firewall for AI models.

Rules enforced:
- Model must be signed (no unsigned models)
- Signature must be from a trusted signer
- Model version must meet minimum requirements
- Model must not be revoked
- Threshold requirement must be met
- Artifact must not be expired (optional TTL)
"""

import time
from typing import List, Optional, Tuple
from dataclasses import dataclass, field


# ── Policy Configuration ──────────────────────────────────────────────────────

@dataclass
class PolicyConfig:
    """
    Configuration for the policy engine.
    All rules are checked during model verification.
    """

    # Signing requirements
    require_signed:          bool       = True
    minimum_signers:         int        = 2
    trusted_signer_ids:      List[str]  = field(default_factory=list)
    require_all_trusted:     bool       = False   # if True, ALL signers must be in trusted list

    # Version requirements
    minimum_version:         Optional[str] = None  # e.g. "1.0.0"
    blocked_versions:        List[str]     = field(default_factory=list)

    # Expiry
    max_artifact_age_days:   Optional[int] = None  # None = no expiry

    # Revocation
    check_revocation:        bool = True

    # Allowed model names (empty = allow all)
    allowed_model_names:     List[str] = field(default_factory=list)


# ── Policy Violation ──────────────────────────────────────────────────────────

@dataclass
class PolicyViolation:
    """Represents a single policy rule violation."""
    rule:    str
    reason:  str
    fatal:   bool = True   # fatal violations block execution entirely


# ── Policy Engine ─────────────────────────────────────────────────────────────

class PolicyEngine:
    """
    Evaluates a signed model artifact against a set of policy rules.

    Usage:
        engine = PolicyEngine(config)
        allowed, violations = engine.evaluate(artifact, ledger)
        if not allowed:
            raise RuntimeError("Model blocked by policy")
    """

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()

    def evaluate(
        self,
        artifact: dict,
        ledger=None,        # TamperEvidentLedger instance (optional)
    ) -> Tuple[bool, List[PolicyViolation]]:
        """
        Run all policy checks against a signed artifact.

        Returns:
            (allowed, list_of_violations)
            allowed is False if ANY fatal violation exists
        """
        violations = []

        violations += self._check_signed(artifact)
        violations += self._check_threshold(artifact)
        violations += self._check_trusted_signers(artifact)
        violations += self._check_version(artifact)
        violations += self._check_expiry(artifact)
        violations += self._check_model_name(artifact)

        if ledger and self.config.check_revocation:
            violations += self._check_revocation(artifact, ledger)

        fatal_violations = [v for v in violations if v.fatal]
        allowed          = len(fatal_violations) == 0

        return allowed, violations

    # ── Individual rule checks ────────────────────────────────────────────────

    def _check_signed(self, artifact: dict) -> List[PolicyViolation]:
        """Rule: model must have a threshold signature block."""
        if not self.config.require_signed:
            return []

        if "threshold_signature" not in artifact:
            return [PolicyViolation(
                rule   = "REQUIRE_SIGNED",
                reason = "Model has no threshold signature — unsigned models are not allowed",
                fatal  = True,
            )]

        sigs = artifact["threshold_signature"].get("signatures", {})
        if not sigs:
            return [PolicyViolation(
                rule   = "REQUIRE_SIGNED",
                reason = "Signature block is empty",
                fatal  = True,
            )]

        return []

    def _check_threshold(self, artifact: dict) -> List[PolicyViolation]:
        """Rule: minimum number of signers must have signed."""
        sigs = artifact.get("threshold_signature", {}).get("signatures", {})
        count = len(sigs)

        if count < self.config.minimum_signers:
            return [PolicyViolation(
                rule   = "MINIMUM_SIGNERS",
                reason = f"Only {count} signer(s) — policy requires at least {self.config.minimum_signers}",
                fatal  = True,
            )]

        return []

    def _check_trusted_signers(self, artifact: dict) -> List[PolicyViolation]:
        """Rule: signers must be in the trusted list (if configured)."""
        if not self.config.trusted_signer_ids:
            return []  # No trusted list configured — allow anyone

        signed_by    = set(artifact.get("signed_by", []))
        trusted      = set(self.config.trusted_signer_ids)
        untrusted    = signed_by - trusted

        if self.config.require_all_trusted and untrusted:
            return [PolicyViolation(
                rule   = "TRUSTED_SIGNERS",
                reason = f"Untrusted signers present: {untrusted}",
                fatal  = True,
            )]

        # Check that at least minimum_signers are trusted
        trusted_present = signed_by & trusted
        if len(trusted_present) < self.config.minimum_signers:
            return [PolicyViolation(
                rule   = "TRUSTED_SIGNERS",
                reason = f"Only {len(trusted_present)} trusted signer(s) — need {self.config.minimum_signers}",
                fatal  = True,
            )]

        return []

    def _check_version(self, artifact: dict) -> List[PolicyViolation]:
        """Rule: version must meet minimum and not be blocked."""
        violations = []
        version    = artifact.get("metadata", {}).get("version", "0.0.0")

        # Check blocked versions
        if version in self.config.blocked_versions:
            violations.append(PolicyViolation(
                rule   = "BLOCKED_VERSION",
                reason = f"Version {version} is explicitly blocked",
                fatal  = True,
            ))

        # Check minimum version using simple tuple comparison
        if self.config.minimum_version:
            def parse(v):
                try:
                    return tuple(int(x) for x in v.split("."))
                except Exception:
                    return (0,)

            if parse(version) < parse(self.config.minimum_version):
                violations.append(PolicyViolation(
                    rule   = "MINIMUM_VERSION",
                    reason = f"Version {version} is below minimum {self.config.minimum_version}",
                    fatal  = True,
                ))

        return violations

    def _check_expiry(self, artifact: dict) -> List[PolicyViolation]:
        """Rule: artifact must not be older than max_artifact_age_days."""
        if not self.config.max_artifact_age_days:
            return []

        timestamp_str = artifact.get("metadata", {}).get("timestamp", "")
        if not timestamp_str:
            return [PolicyViolation(
                rule   = "EXPIRY",
                reason = "Artifact has no timestamp — cannot verify expiry",
                fatal  = True,
            )]

        try:
            import datetime
            artifact_time = datetime.datetime.strptime(
                timestamp_str, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=datetime.timezone.utc)

            now     = datetime.datetime.now(datetime.timezone.utc)
            age     = (now - artifact_time).days

            if age > self.config.max_artifact_age_days:
                return [PolicyViolation(
                    rule   = "EXPIRY",
                    reason = f"Artifact is {age} days old — max allowed is {self.config.max_artifact_age_days}",
                    fatal  = True,
                )]
        except Exception as e:
            return [PolicyViolation(
                rule   = "EXPIRY",
                reason = f"Could not parse artifact timestamp: {e}",
                fatal  = False,
            )]

        return []

    def _check_revocation(self, artifact: dict, ledger) -> List[PolicyViolation]:
        """Rule: model must not be revoked in the ledger."""
        artifact_id = artifact.get("metadata", {}).get("artifact_id", "")

        if ledger.is_revoked(artifact_id):
            return [PolicyViolation(
                rule   = "REVOCATION",
                reason = f"Artifact {artifact_id} has been revoked",
                fatal  = True,
            )]

        return []

    def _check_model_name(self, artifact: dict) -> List[PolicyViolation]:
        """Rule: model name must be in allowed list (if configured)."""
        if not self.config.allowed_model_names:
            return []

        name = artifact.get("metadata", {}).get("model_name", "")
        if name not in self.config.allowed_model_names:
            return [PolicyViolation(
                rule   = "ALLOWED_MODELS",
                reason = f"Model '{name}' is not in the allowed models list",
                fatal  = True,
            )]

        return []

    # ── Reporting ─────────────────────────────────────────────────────────────

    def violations_report(self, violations: List[PolicyViolation]) -> dict:
        """Format violations into a structured report for API/UI."""
        return {
            "total":   len(violations),
            "fatal":   len([v for v in violations if v.fatal]),
            "details": [
                {
                    "rule":   v.rule,
                    "reason": v.reason,
                    "fatal":  v.fatal,
                }
                for v in violations
            ],
        }
