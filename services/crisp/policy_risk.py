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
            governance_body
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
            COUNT(*) FILTER (WHERE sentiment = 'positive') AS positive_feedback,
            COUNT(*) FILTER (WHERE consent_given = TRUE) AS consent_count
        FROM stakeholder_feedback
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_article_6_indicators(conn, location_id: str) -> Dict[str, Any]:
    """Query Article 6 readiness indicators from available data sources.

    Article 6 of the Paris Agreement covers international carbon market
    cooperation. Key indicators:
    - NDC participation: whether the host country has an active NDC
    - Corresponding adjustment: whether corresponding adjustments are
      documented for bilateral Article 6.2 trades
    - Article 6.4 registry engagement: whether the project is registered
      or engaging with the Article 6.4 crediting mechanism

    Since there is no dedicated table, we derive signals from:
    - location.metadata (may contain ndc_participation, article_6 fields)
    - credit_retirement (retirement reasons indicating international transfer)
    - attestation_record (claim_data may reference Article 6)
    - farm_registry_record (metadata may reference registry engagement)
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1. Check location metadata for Article 6 fields
    cur.execute("""
        SELECT metadata FROM location WHERE id = %s
    """, (location_id,))
    loc_row = dict(cur.fetchone() or {})
    loc_meta = loc_row.get("metadata") or {}
    ndc_status = loc_meta.get("ndc_participation_status")
    adj_status = loc_meta.get("corresponding_adjustment_status")
    article64_status = loc_meta.get("article_6_4_registry_status")

    # 2. Check credit retirement for international transfer signals
    cur.execute("""
        SELECT COUNT(*) AS international_retirements
        FROM credit_retirement
        WHERE location_id = %s
          AND status = 'published'
          AND (
            retirement_reason ILIKE '%%article 6%%'
            OR retirement_reason ILIKE '%%corresponding adjustment%%'
            OR retirement_reason ILIKE '%%international transfer%%'
            OR retirement_reason ILIKE '%%bilateral%%'
          )
    """, (location_id,))
    retire_row = dict(cur.fetchone() or {})
    international_retirements = int(retire_row.get("international_retirements") or 0)

    # 3. Check attestation records for Article 6 claims
    cur.execute("""
        SELECT COUNT(*) AS article6_attestations
        FROM attestation_record
        WHERE subject_id = %s
          AND subject_type = 'location'
          AND status IN ('verified', 'published')
          AND (
            claim_data::text ILIKE '%%article 6%%'
            OR claim_data::text ILIKE '%%corresponding adjustment%%'
            OR claim_type ILIKE '%%article_6%%'
          )
    """, (location_id,))
    attest_row = dict(cur.fetchone() or {})
    article6_attestations = int(attest_row.get("article6_attestations") or 0)

    # 4. Check farm registry for registry engagement
    cur.execute("""
        SELECT COUNT(*) AS registry_engagements
        FROM farm_registry_record
        WHERE location_id = %s
          AND status IN ('verified', 'published')
          AND (
            registry_slug ILIKE '%%article%%'
            OR metadata::text ILIKE '%%article 6%%'
            OR credits_registries::text ILIKE '%%article%%'
          )
    """, (location_id,))
    reg_row = dict(cur.fetchone() or {})
    registry_engagements = int(reg_row.get("registry_engagements") or 0)

    cur.close()

    return {
        "ndc_participation_status": ndc_status,
        "corresponding_adjustment_status": adj_status,
        "article_6_4_registry_status": article64_status,
        "international_retirements": international_retirements,
        "article6_attestations": article6_attestations,
        "registry_engagements": registry_engagements,
    }


def _score_article_6(indicators: Dict[str, Any]) -> Optional[float]:
    """Score Article 6 readiness on a 0-1 scale (higher = more ready).

    Scoring logic:
    - NDC participation: 0.3 weight (active=1.0, submitted=0.6, none=0.0)
    - Corresponding adjustment: 0.3 weight (confirmed=1.0, pending=0.5, none=0.0)
    - Article 6.4 registry: 0.2 weight (registered=1.0, engaged=0.5, none=0.0)
    - Supporting signals: 0.2 weight (retirements + attestations + registry)

    Returns None if no data is available (graceful degradation).
    """
    has_any_data = (
        indicators.get("ndc_participation_status") is not None
        or indicators.get("corresponding_adjustment_status") is not None
        or indicators.get("article_6_4_registry_status") is not None
        or indicators.get("international_retirements", 0) > 0
        or indicators.get("article6_attestations", 0) > 0
        or indicators.get("registry_engagements", 0) > 0
    )
    if not has_any_data:
        return None

    scores = []

    # NDC participation (0.3 weight)
    ndc = (indicators.get("ndc_participation_status") or "").lower()
    if ndc in ("active", "ratified", "implemented"):
        scores.append(("ndc", 1.0, 0.3))
    elif ndc in ("submitted", "pending", "draft"):
        scores.append(("ndc", 0.6, 0.3))
    elif ndc:
        scores.append(("ndc", 0.2, 0.3))
    else:
        scores.append(("ndc", 0.0, 0.3))

    # Corresponding adjustment (0.3 weight)
    adj = (indicators.get("corresponding_adjustment_status") or "").lower()
    if adj in ("confirmed", "approved", "completed"):
        scores.append(("adj", 1.0, 0.3))
    elif adj in ("pending", "submitted", "in_progress"):
        scores.append(("adj", 0.5, 0.3))
    elif adj:
        scores.append(("adj", 0.2, 0.3))
    else:
        scores.append(("adj", 0.0, 0.3))

    # Article 6.4 registry (0.2 weight)
    reg = (indicators.get("article_6_4_registry_status") or "").lower()
    if reg in ("registered", "active", "approved"):
        scores.append(("reg", 1.0, 0.2))
    elif reg in ("engaged", "pending", "submitted"):
        scores.append(("reg", 0.5, 0.2))
    elif reg:
        scores.append(("reg", 0.2, 0.2))
    else:
        scores.append(("reg", 0.0, 0.2))

    # Supporting signals (0.2 weight)
    signals = 0.0
    if indicators.get("international_retirements", 0) > 0:
        signals += 0.4
    if indicators.get("article6_attestations", 0) > 0:
        signals += 0.3
    if indicators.get("registry_engagements", 0) > 0:
        signals += 0.3
    scores.append(("signals", min(signals, 1.0), 0.2))

    total_weight = sum(w for _, _, w in scores)
    if total_weight == 0:
        return 0.0

    weighted = sum(s * w for _, s, w in scores) / total_weight
    return round(max(0.0, min(1.0, weighted)), 2)


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

    # Stakeholder satisfaction (positive feedback ratio)
    total = int(feedback.get("total_feedback", 0) or 0)
    positive = int(feedback.get("positive_feedback", 0) or 0)
    if total > 0:
        scores.append(positive / total)

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
    article6_indicators = _query_article_6_indicators(conn, location_id)

    # Score each sub-factor (0-1 strength, higher = lower risk)
    policy_strength = _score_national_policy(certification)
    carbon_rights = _score_carbon_rights(land_tenure)
    land_tenure_score = _score_land_tenure(land_tenure)
    community_alignment = _score_community_alignment(governance, feedback)
    certification_risk = _score_certification_risk(barriers)
    article_6_readiness = _score_article_6(article6_indicators)

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
        "article_6_readiness": round(article_6_readiness, 3) if article_6_readiness is not None else None,
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
