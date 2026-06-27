"""Confidence labels for EBF scorecards."""

from __future__ import annotations


def score_confidence_label(evidence_count: int, evidence_maturity: int, public_safe_evidence_count: int = 0) -> str:
    """Return a conservative EBF score confidence label."""
    if evidence_count <= 0 or evidence_maturity <= 1:
        return "insufficient_evidence"
    if evidence_maturity >= 5 and evidence_count >= 3 and public_safe_evidence_count >= 2:
        return "high"
    if evidence_maturity >= 4 and evidence_count >= 2 and public_safe_evidence_count >= 1:
        return "moderate"
    return "low"


def scorecard_confidence_label(score_labels: list[str]) -> str:
    """Roll pillar confidence into a conservative scorecard confidence label."""
    if not score_labels:
        return "insufficient_evidence"
    if any(label == "insufficient_evidence" for label in score_labels):
        return "insufficient_evidence"
    if all(label == "high" for label in score_labels):
        return "high"
    if all(label in {"high", "moderate"} for label in score_labels):
        return "moderate"
    return "low"
