"""Policy and legal risk scoring module.

Adapted from SW-CRISP Annexure 3.  Assesses risks at the national/jurisdictional
and project-specific policy levels using indicators for policy framework strength,
carbon rights clarity, land tenure, and community alignment.

Scoring approach:
1. Query certification records, adoption barriers, land stewardship
2. Score each sub-factor 0-1 based on presence/strength
3. Weighted average converted to 0-100 risk score
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras

from .models import DimensionScore
from .normalization import clamp_risk_score, normalize_to_risk


def _query_certification_status(conn, location_id: str) -> Dict[str, Any]:
    """Get organic certification status."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            standard,
            status,
            certification_date,
            expiry_date
        FROM organic_certification_record
        WHERE location_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_adoption_barriers(conn, location_id: str) -> list:
    """Get regulatory and governance barriers."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            barrier_category,
            severity,
            likelihood,
            mitigation_plan
        FROM adoption_barrier_assessment
        WHERE location_id = %s
        AND barrier_category IN ('regulatory', 'dao_governance', 'other')
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def _query_land_tenure(conn, location_id: str) -> Dict[str, Any]:
    """Get land tenure and stewardship information."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            stewardship_model,
            landlord_dependency_risk,
            anti_speculation_terms
        FROM land_stewardship_commitment
        WHERE location_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_community_governance(conn, location_id: str) -> Dict[str, Any]:
    """Get community governance and inclusion data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            representation_coverage_pct,
            marginalized_voice_count,
            decision_method
        FROM governance_inclusion_observation
        WHERE location_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_stakeholder_feedback_summary(conn, location_id: str) -> Dict[str, Any]:
    """Get stakeholder feedback summary for community alignment."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS total_feedback,
            COALESCE(AVG(satisfaction_score), 0) AS avg_satisfaction,
            COUNT(*) FILTER (WHERE consent_given = TRUE) AS consent_count
        FROM stakeholder_feedback
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _score_national_policy(certification: Dict[str, Any]) -> float:
    """Score national policy framework strength (0-1, higher = stronger)."""
    status = certification.get("status", "")
    if status == "certified":
        return 1.0
    elif status == "inspected":
        return 0.75
    elif status == "submitted":
        return 0.5
    elif status in ("planning", "preparing"):
        return 0.25
    return 0.0


def _score_carbon_rights(land_tenure: Dict[str, Any]) -> float:
    """Score carbon rights clarity (0-1, higher = clearer)."""
    model = land_tenure.get("stewardship_model", "")
    if model in ("community_owned", "individual_owned", "cooperative"):
        return 1.0
    elif model in ("leased", "managed"):
        return 0.75
    elif model in ("shared", "customary"):
        return 0.5
    elif model:
        return 0.25
    return 0.0


def _score_land_tenure(land_tenure: Dict[str, Any]) -> float:
    """Score land tenure security (0-1, higher = more secure)."""
    risk = land_tenure.get("landlord_dependency_risk", "")
    anti_spec = land_tenure.get("anti_speculation_terms", False)
    score = 0.0
    if risk == "low":
        score = 1.0
    elif risk == "medium":
        score = 0.6
    elif risk == "high":
        score = 0.3
    elif risk == "critical":
        score = 0.1
    else:
        score = 0.5  # Unknown = moderate

    if anti_spec:
        score = min(1.0, score + 0.1)

    return score


def _score_community_alignment(
    governance: Dict[str, Any],
    feedback: Dict[str, Any],
) -> float:
    """Score community alignment (0-1, higher = better aligned)."""
    scores = []

    # Representation coverage
    coverage = float(governance.get("representation_coverage_pct", 0) or 0)
    scores.append(min(1.0, coverage / 100.0))

    # Marginalized voice inclusion
    voices = int(governance.get("marginalized_voice_count", 0) or 0)
    if voices > 5:
        scores.append(1.0)
    elif voices > 2:
        scores.append(0.7)
    elif voices > 0:
        scores.append(0.4)
    else:
        scores.append(0.0)

    # Stakeholder satisfaction
    satisfaction = float(feedback.get("avg_satisfaction", 0) or 0)
    if satisfaction > 0:
        scores.append(min(1.0, satisfaction / 10.0))

    return sum(scores) / len(scores) if scores else 0.0


def _score_certification_risk(barriers: list) -> float:
    """Score certification/regulatory risk (0-1, higher = more risk)."""
    if not barriers:
        return 0.25  # No barriers documented = moderate risk

    severity_scores = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
    max_risk = 0.0
    for b in barriers:
        sev = b.get("severity", "medium")
        risk = severity_scores.get(sev, 0.5)
        has_mitigation = bool(b.get("mitigation_plan"))
        if has_mitigation:
            risk *= 0.5
        max_risk = max(max_risk, risk)

    return max_risk


def compute_policy_risk(
    conn,
    location_id: str,
) -> DimensionScore:
    """Compute policy and legal risk score for a location.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.

    Returns:
        DimensionScore with risk_score 0-100 (higher = more risk).
    """
    certification = _query_certification_status(conn, location_id)
    barriers = _query_adoption_barriers(conn, location_id)
    land_tenure = _query_land_tenure(conn, location_id)
    governance = _query_community_governance(conn, location_id)
    feedback = _query_stakeholder_feedback_summary(conn, location_id)

    # Score each sub-factor (0-1 strength, higher = lower risk)
    policy_strength = _score_national_policy(certification)
    carbon_rights = _score_carbon_rights(land_tenure)
    land_tenure_score = _score_land_tenure(land_tenure)
    community_alignment = _score_community_alignment(governance, feedback)
    certification_risk = _score_certification_risk(barriers)

    # Invert to risk: 1 - strength = risk
    policy_risk = 1.0 - policy_strength
    carbon_rights_risk = 1.0 - carbon_rights
    land_tenure_risk = 1.0 - land_tenure_score
    community_risk = 1.0 - community_alignment

    # Weighted average of risk factors
    sub_scores = {
        "national_policy": policy_risk,
        "carbon_rights": carbon_rights_risk,
        "land_tenure": land_tenure_risk,
        "community_alignment": community_risk,
        "certification": certification_risk,
    }
    weights = {
        "national_policy": 0.25,
        "carbon_rights": 0.20,
        "land_tenure": 0.20,
        "community_alignment": 0.20,
        "certification": 0.15,
    }
    weighted_risk = sum(sub_scores[k] * weights[k] for k in sub_scores)
    risk_score = clamp_risk_score(weighted_risk * 100)

    # Evidence maturity
    evidence_level = 1
    if certification:
        evidence_level = 3
    if land_tenure:
        evidence_level = min(evidence_level + 1, 6)
    if governance:
        evidence_level = min(evidence_level + 1, 6)
    if barriers:
        evidence_level = min(evidence_level + 1, 6)

    from .config import CONFIDENCE_THRESHOLDS
    confidence = CONFIDENCE_THRESHOLDS.get(evidence_level, "insufficient_evidence")

    factors = {
        "policy_strength": round(policy_strength, 3),
        "carbon_rights_clarity": round(carbon_rights, 3),
        "land_tenure_security": round(land_tenure_score, 3),
        "community_alignment": round(community_alignment, 3),
        "certification_risk": round(certification_risk, 3),
        "regulatory_barriers_count": len(barriers),
        "certification_status": certification.get("status"),
        "stewardship_model": land_tenure.get("stewardship_model"),
    }

    return DimensionScore(
        dimension_key="policy",
        dimension_name="Policy & Legal Risk",
        risk_score=clamp_risk_score(risk_score),
        confidence_level=confidence,
        evidence_maturity_level=evidence_level,
        weight=0.0,
        factors=factors,
        evidence_summary=f"Policy strength {policy_strength:.2f}, carbon rights {carbon_rights:.2f}, land tenure {land_tenure_score:.2f}, community {community_alignment:.2f}",
    )
