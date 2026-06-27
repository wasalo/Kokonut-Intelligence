"""Evidence maturity gates for EBF score publication."""

from __future__ import annotations


def public_score_allowed(evidence_maturity_level: int, has_evidence_link: bool) -> bool:
    """Return true when a non-carbon EBF score can be public-safe."""
    return int(evidence_maturity_level) >= 4 and has_evidence_link


def public_carbon_score_allowed(evidence_maturity_level: int, has_evidence_link: bool) -> bool:
    """Return true when a carbon EBF score can be public-safe."""
    return int(evidence_maturity_level) == 6 and has_evidence_link


def linked_carbon_claim_allowed(claim: dict | None) -> bool:
    """Return true when a linked impact claim satisfies public carbon rules."""
    if not claim:
        return False
    return (
        claim.get("claim_category") == "carbon"
        and claim.get("claim_type") == "third_party_verified_claim"
        and int(claim.get("evidence_maturity") or 0) == 6
        and claim.get("status") == "published"
        and bool(str(claim.get("external_verifier") or "").strip())
        and bool(str(claim.get("methodology_ref") or "").strip())
    )


def score_publication_gate(
    pillar_key: str,
    evidence_maturity_level: int,
    has_evidence_link: bool,
    linked_impact_claim: dict | None = None,
) -> tuple[bool, str]:
    """Assess publication readiness for one EBF pillar score."""
    if pillar_key == "carbon_sequestration":
        allowed = public_carbon_score_allowed(evidence_maturity_level, has_evidence_link) and linked_carbon_claim_allowed(linked_impact_claim)
        return (allowed, "allowed" if allowed else "public carbon scores require Level 6 evidence, an evidence link, and a published third-party verified carbon impact claim")
    allowed = public_score_allowed(evidence_maturity_level, has_evidence_link)
    return (allowed, "allowed" if allowed else "public scores require Level 4 evidence or higher and an evidence link")


def scorecard_publication_gate(evidence_maturity_level: int, pillar_results: list[tuple[bool, str]]) -> tuple[bool, list[str]]:
    """Assess publication readiness for a full EBF scorecard."""
    reasons: list[str] = []
    if int(evidence_maturity_level) < 4:
        reasons.append("scorecard requires evidence maturity Level 4 or higher")
    reasons.extend(reason for allowed, reason in pillar_results if not allowed)
    return (not reasons, reasons)
