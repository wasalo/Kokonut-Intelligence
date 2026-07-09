"""Implementation risk scoring module.

Adapted from SW-CRISP Annexure 4.  Analyzes the strength of the farm operator
(track record, team capability, network, community alignment, transparency)
to assess delivery risk.

Scoring approach:
1. Query onboarding profile, regenerative practices, stakeholder feedback,
   governance inclusion, training data
2. Score sub-factors 0-1 (higher = stronger/lower risk)
3. Invert to risk and weight
4. Convert to 0-100 risk score
"""

from __future__ import annotations

from typing import Any, Dict

import psycopg2
import psycopg2.extras

from .models import DimensionScore
from .normalization import clamp_risk_score


def _query_onboarding(conn, location_id: str) -> Dict[str, Any]:
    """Get farm onboarding profile."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            readiness_score,
            risk_level,
            training_completed_pct,
            infrastructure_readiness,
            community_engagement_level,
            implementation_partners_count
        FROM farm_onboarding_profile
        WHERE location_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_practices(conn, location_id: str) -> Dict[str, Any]:
    """Get regenerative practice checklist status."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS total_principles,
            COUNT(*) FILTER (WHERE score >= 3) AS adopted_principles,
            COALESCE(AVG(score), 0) AS avg_practice_score,
            COALESCE(SUM(score), 0) AS total_score
        FROM regenerative_practice_checklist
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_governance_inclusion(conn, location_id: str) -> Dict[str, Any]:
    """Get governance inclusion data."""
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


def _query_stakeholder_satisfaction(conn, location_id: str) -> Dict[str, Any]:
    """Get stakeholder feedback satisfaction."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS feedback_count,
            COALESCE(AVG(satisfaction_score), 0) AS avg_satisfaction,
            COUNT(*) FILTER (WHERE status = 'published') AS published_count
        FROM stakeholder_feedback
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_training(conn, location_id: str) -> Dict[str, Any]:
    """Get training activity summary."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS training_count,
            COALESCE(SUM(COALESCE(participants, 0)), 0) AS total_participants
        FROM training_event
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _score_track_record(
    onboarding: Dict[str, Any],
    practices: Dict[str, Any],
) -> float:
    """Score track record (0-1, higher = stronger)."""
    scores = []

    # Onboarding readiness
    readiness = float(onboarding.get("readiness_score", 0) or 0)
    scores.append(min(1.0, readiness / 10.0))

    # Practice adoption
    total_principles = int(practices.get("total_principles", 0) or 0)
    adopted = int(practices.get("adopted_principles", 0) or 0)
    if total_principles > 0:
        scores.append(adopted / total_principles)
    else:
        scores.append(0.0)

    # Practice score average
    avg_score = float(practices.get("avg_practice_score", 0) or 0)
    scores.append(min(1.0, avg_score / 5.0))

    return sum(scores) / len(scores) if scores else 0.0


def _score_team_strength(
    onboarding: Dict[str, Any],
    training: Dict[str, Any],
) -> float:
    """Score team strength (0-1, higher = stronger)."""
    scores = []

    # Training completion
    training_pct = float(onboarding.get("training_completed_pct", 0) or 0)
    scores.append(min(1.0, training_pct / 100.0))

    # Training activity
    training_count = int(training.get("training_count", 0) or 0)
    if training_count > 10:
        scores.append(1.0)
    elif training_count > 5:
        scores.append(0.7)
    elif training_count > 0:
        scores.append(0.4)
    else:
        scores.append(0.0)

    # Community engagement
    engagement = onboarding.get("community_engagement_level", "")
    if engagement in ("high", "active"):
        scores.append(1.0)
    elif engagement in ("medium", "moderate"):
        scores.append(0.6)
    elif engagement in ("low", "minimal"):
        scores.append(0.3)
    else:
        scores.append(0.2)

    return sum(scores) / len(scores) if scores else 0.0


def _score_network_strength(onboarding: Dict[str, Any]) -> float:
    """Score network strength (0-1, higher = stronger)."""
    partners = int(onboarding.get("implementation_partners_count", 0) or 0)
    infra = onboarding.get("infrastructure_readiness", "")

    partner_score = min(1.0, partners / 5.0)
    if infra in ("ready", "complete", "high"):
        infra_score = 1.0
    elif infra in ("partial", "medium"):
        infra_score = 0.6
    elif infra in ("minimal", "low"):
        infra_score = 0.3
    else:
        infra_score = 0.2

    return (partner_score + infra_score) / 2


def _score_transparency(
    governance: Dict[str, Any],
    feedback: Dict[str, Any],
) -> float:
    """Score transparency (0-1, higher = more transparent)."""
    scores = []

    # Governance representation
    coverage = float(governance.get("representation_coverage_pct", 0) or 0)
    scores.append(min(1.0, coverage / 100.0))

    # Decision method transparency
    method = governance.get("decision_method", "")
    if method in ("consensus", "consent", "hybrid"):
        scores.append(1.0)
    elif method in ("token_vote", "multisig"):
        scores.append(0.7)
    elif method:
        scores.append(0.4)
    else:
        scores.append(0.0)

    # Stakeholder feedback volume
    feedback_count = int(feedback.get("feedback_count", 0) or 0)
    published = int(feedback.get("published_count", 0) or 0)
    if feedback_count > 5:
        scores.append(min(1.0, published / feedback_count))
    elif feedback_count > 0:
        scores.append(0.5)
    else:
        scores.append(0.0)

    return sum(scores) / len(scores) if scores else 0.0


def compute_implementation_risk(
    conn,
    location_id: str,
) -> DimensionScore:
    """Compute implementation/developer risk score for a location.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.

    Returns:
        DimensionScore with risk_score 0-100 (higher = more risk).
    """
    onboarding = _query_onboarding(conn, location_id)
    practices = _query_practices(conn, location_id)
    governance = _query_governance_inclusion(conn, location_id)
    feedback = _query_stakeholder_satisfaction(conn, location_id)
    training = _query_training(conn, location_id)

    # Score sub-factors (0-1 strength, higher = lower risk)
    track_record = _score_track_record(onboarding, practices)
    team_strength = _score_team_strength(onboarding, training)
    network_strength = _score_network_strength(onboarding)
    transparency = _score_transparency(governance, feedback)

    # Community alignment from governance inclusion
    community_coverage = float(governance.get("representation_coverage_pct", 0) or 0)
    community_alignment = min(1.0, community_coverage / 100.0)

    # Invert to risk
    sub_risks = {
        "track_record": 1.0 - track_record,
        "team_strength": 1.0 - team_strength,
        "network_strength": 1.0 - network_strength,
        "community_alignment": 1.0 - community_alignment,
        "transparency": 1.0 - transparency,
    }
    weights = {
        "track_record": 0.25,
        "team_strength": 0.25,
        "network_strength": 0.20,
        "community_alignment": 0.15,
        "transparency": 0.15,
    }
    weighted_risk = sum(sub_risks[k] * weights[k] for k in sub_risks)
    risk_score = clamp_risk_score(weighted_risk * 100)

    # Evidence maturity
    evidence_level = 1
    if onboarding:
        evidence_level = 3
    if practices and int(practices.get("total_principles", 0) or 0) > 0:
        evidence_level = min(evidence_level + 1, 6)
    if governance:
        evidence_level = min(evidence_level + 1, 6)

    from .config import CONFIDENCE_THRESHOLDS
    confidence = CONFIDENCE_THRESHOLDS.get(evidence_level, "insufficient_evidence")

    factors = {
        "track_record_strength": round(track_record, 3),
        "team_strength": round(team_strength, 3),
        "network_strength": round(network_strength, 3),
        "community_alignment": round(community_alignment, 3),
        "transparency": round(transparency, 3),
        "onboarding_readiness": float(onboarding.get("readiness_score", 0) or 0),
        "training_completed_pct": float(onboarding.get("training_completed_pct", 0) or 0),
        "practice_adoption_pct": (
            round(int(practices.get("adopted_principles", 0) or 0) / max(1, int(practices.get("total_principles", 1) or 1)) * 100, 1)
        ),
        "implementation_partners": int(onboarding.get("implementation_partners_count", 0) or 0),
    }

    return DimensionScore(
        dimension_key="implementation",
        dimension_name="Implementation Risk",
        risk_score=clamp_risk_score(risk_score),
        confidence_level=confidence,
        evidence_maturity_level=evidence_level,
        weight=0.0,
        factors=factors,
        evidence_summary=f"Track record {track_record:.2f}, team {team_strength:.2f}, network {network_strength:.2f}, community {community_alignment:.2f}, transparency {transparency:.2f}",
    )
