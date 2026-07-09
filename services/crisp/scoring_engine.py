"""CRISP scoring engine — composite aggregation and rating.

Orchestrates the five dimension scoring modules, applies configurable
weights (per-location or default), computes composite score, assigns
AAA-D rating, and persists results to the database.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .config import (
    CONFIDENCE_THRESHOLDS,
    CRISP_VERSION,
    DEFAULT_WEIGHTS,
    RATING_BANDS,
)
from .models import CompositeRating, DimensionScore
from .normalization import weighted_average_risk


def _query_location_weights(conn, location_id: str) -> Dict[str, float]:
    """Query per-location weight overrides, falling back to defaults."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            cd.dimension_key,
            clw.weight
        FROM crisp_location_weight clw
        JOIN crisp_risk_dimension cd ON cd.id = clw.dimension_id
        WHERE clw.location_id = %s
        AND clw.status = 'active'
        AND cd.status = 'active'
    """, (location_id,))
    rows = {r["dimension_key"]: float(r["weight"]) for r in cur.fetchall()}
    cur.close()

    # Merge with defaults (DB overrides take precedence)
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(rows)

    # Normalize weights to sum to 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    return weights


def _assign_rating(composite_score: float) -> str:
    """Assign AAA-D rating based on composite score."""
    for rating, (low, high) in RATING_BANDS.items():
        if low <= composite_score <= high:
            return rating
    return "D"


def _compute_confidence(dimensions: List[DimensionScore]) -> str:
    """Compute overall confidence from dimension evidence maturity."""
    if not dimensions:
        return "insufficient_evidence"
    min_level = min(d.evidence_maturity_level for d in dimensions)
    return CONFIDENCE_THRESHOLDS.get(min_level, "insufficient_evidence")


def compute_all_dimensions(
    conn,
    location_id: str,
    dimensions: Optional[List[str]] = None,
    **kwargs,
) -> List[DimensionScore]:
    """Compute all or selected CRISP risk dimensions.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.
        dimensions: List of dimension keys to compute. None = all.
        **kwargs: Additional arguments passed to individual scorers.

    Returns:
        List of DimensionScore objects.
    """
    all_dims = {
        "carbon_yield": ("carbon_yield", "compute_carbon_yield_risk"),
        "climate": ("climate", "compute_climate_risk"),
        "policy": ("policy", "compute_policy_risk"),
        "financial": ("financial", "compute_financial_risk"),
        "implementation": ("implementation", "compute_implementation_risk"),
    }

    keys = dimensions or list(all_dims.keys())
    results = []

    for key in keys:
        if key not in all_dims:
            continue

        module_name, func_name = all_dims[key]

        if key == "carbon_yield":
            from .carbon_yield import compute_carbon_yield_risk
            score = compute_carbon_yield_risk(conn, location_id, **kwargs)
        elif key == "climate":
            from .climate_risk import compute_climate_risk
            ssp = kwargs.get("ssp_scenario", "SSP2")
            score = compute_climate_risk(conn, location_id, ssp_scenario=ssp)
        elif key == "policy":
            from .policy_risk import compute_policy_risk
            score = compute_policy_risk(conn, location_id)
        elif key == "financial":
            from .financial_risk import compute_financial_risk
            vintage = kwargs.get("vintage_year")
            score = compute_financial_risk(conn, location_id, vintage_year=vintage)
        elif key == "implementation":
            from .implementation_risk import compute_implementation_risk
            score = compute_implementation_risk(conn, location_id)

        results.append(score)

    return results


def compute_composite_rating(
    conn,
    location_id: str,
    period_start: str,
    period_end: str,
    dimensions: Optional[List[str]] = None,
    methodology_version: Optional[str] = None,
    **kwargs,
) -> CompositeRating:
    """Compute full CRISP composite rating for a location.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.
        period_start: Assessment period start date (YYYY-MM-DD).
        period_end: Assessment period end date (YYYY-MM-DD).
        dimensions: List of dimension keys to compute. None = all.
        methodology_version: Version string. If None, uses CRISP_VERSION.
        **kwargs: Additional arguments passed to individual scorers.

    Returns:
        CompositeRating with all dimension scores and composite rating.
    """
    weights = _query_location_weights(conn, location_id)
    dim_scores = compute_all_dimensions(conn, location_id, dimensions, **kwargs)

    # Apply weights to each dimension
    for d in dim_scores:
        d.weight = weights.get(d.dimension_key, 0.0)

    # Build score map for composite calculation
    score_map = {d.dimension_key: d.risk_score for d in dim_scores}

    # Compute weighted composite
    composite = weighted_average_risk(score_map, weights)
    rating = _assign_rating(composite)
    confidence = _compute_confidence(dim_scores)

    # Map scores to named fields
    score_fields = {}
    for d in dim_scores:
        field_name = f"{d.dimension_key}_score"
        score_fields[field_name] = d.risk_score

    return CompositeRating(
        location_id=location_id,
        period_start=period_start,
        period_end=period_end,
        carbon_yield_score=score_fields.get("carbon_yield_score"),
        climate_score=score_fields.get("climate_score"),
        policy_score=score_fields.get("policy_score"),
        financial_score=score_fields.get("financial_score"),
        implementation_score=score_fields.get("implementation_score"),
        composite_score=composite,
        rating=rating,
        confidence_level=confidence,
        methodology_version=methodology_version or CRISP_VERSION,
        weights=weights,
        dimensions=dim_scores,
    )


def persist_assessment(conn, rating: CompositeRating) -> str:
    """Persist a CRISP assessment to the database.

    Returns:
        The assessment UUID.
    """
    cur = conn.cursor()

    # Insert master assessment
    cur.execute("""
        INSERT INTO crisp_risk_assessment (
            location_id, period_start, period_end, methodology_version,
            carbon_yield_score, climate_score, policy_score,
            financial_score, implementation_score,
            composite_score, rating, confidence_level,
            score_computed_at, status, metadata
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            NOW(), 'draft', %s
        )
        RETURNING id
    """, (
        rating.location_id,
        rating.period_start,
        rating.period_end,
        rating.methodology_version,
        rating.carbon_yield_score,
        rating.climate_score,
        rating.policy_score,
        rating.financial_score,
        rating.implementation_score,
        rating.composite_score,
        rating.rating,
        rating.confidence_level,
        psycopg2.extras.Json({"weights": rating.weights}),
    ))
    assessment_id = cur.fetchone()[0]

    # Insert per-dimension detail records
    for dim in rating.dimensions:
        if dim.dimension_key == "carbon_yield":
            f = dim.factors
            cur.execute("""
                INSERT INTO crisp_carbon_yield_risk (
                    assessment_id, location_id, risk_score,
                    allometric_source, planting_density_per_ha,
                    mortality_rate_pct, ndvi_pre_project,
                    scenario_minimum, scenario_realistic, scenario_optimistic,
                    ex_ante_estimate, yield_likelihood,
                    evidence_maturity_level, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment_id, rating.location_id, dim.risk_score,
                f.get("allometric_source"), f.get("planting_density_per_ha"),
                f.get("mortality_rate_pct"), f.get("ndvi"),
                f.get("scenario_minimum"), f.get("scenario_realistic"), f.get("scenario_optimistic"),
                f.get("ex_ante_estimate"),
                1.0 - (dim.risk_score / 100.0),
                dim.evidence_maturity_level,
                psycopg2.extras.Json(dim.factors),
            ))

        elif dim.dimension_key == "climate":
            f = dim.factors
            cur.execute("""
                INSERT INTO crisp_climate_risk (
                    assessment_id, location_id, risk_score,
                    drought_risk_score, flood_risk_score, heatwave_risk_score,
                    fire_risk_score, storm_risk_score, water_stress_score,
                    natural_risk_rating, mitigation_factor,
                    climate_catastrophe_factor, ssp_scenario,
                    evidence_maturity_level, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment_id, rating.location_id, dim.risk_score,
                f.get("drought_score"), f.get("flood_score"), f.get("heatwave_score"),
                f.get("fire_score"), f.get("storm_score"), f.get("water_stress_score"),
                f.get("natural_risk_rating"), f.get("mitigation_factor"),
                f.get("mitigated_rating", 0) / 15.0 if f.get("mitigated_rating") else None,
                f.get("ssp_scenario", "SSP2"),
                dim.evidence_maturity_level,
                psycopg2.extras.Json(dim.factors),
            ))

        elif dim.dimension_key == "policy":
            f = dim.factors
            cur.execute("""
                INSERT INTO crisp_policy_risk (
                    assessment_id, location_id, risk_score,
                    national_policy_score, carbon_rights_score, land_tenure_score,
                    community_alignment_score, certification_risk_score,
                    evidence_maturity_level, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment_id, rating.location_id, dim.risk_score,
                1.0 - f.get("policy_strength", 0),
                1.0 - f.get("carbon_rights_clarity", 0),
                1.0 - f.get("land_tenure_security", 0),
                1.0 - f.get("community_alignment", 0),
                f.get("certification_risk", 0),
                dim.evidence_maturity_level,
                psycopg2.extras.Json(dim.factors),
            ))

        elif dim.dimension_key == "financial":
            f = dim.factors
            cur.execute("""
                INSERT INTO crisp_financial_risk (
                    assessment_id, location_id, risk_score,
                    break_even_year, revenue_risk_factor, cost_risk_factor,
                    market_price_risk, liquidity_risk, financial_risk_factor,
                    evidence_maturity_level, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment_id, rating.location_id, dim.risk_score,
                f.get("break_even_month"),
                f.get("revenue_risk"), f.get("cost_risk"),
                f.get("market_price_risk"), f.get("liquidity_risk"),
                f.get("financial_risk_factor"),
                dim.evidence_maturity_level,
                psycopg2.extras.Json(dim.factors),
            ))

        elif dim.dimension_key == "implementation":
            f = dim.factors
            cur.execute("""
                INSERT INTO crisp_implementation_risk (
                    assessment_id, location_id, risk_score,
                    track_record_score, team_strength_score, network_strength_score,
                    community_alignment_score, transparency_score,
                    evidence_maturity_level, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment_id, rating.location_id, dim.risk_score,
                f.get("track_record_strength"), f.get("team_strength"),
                f.get("network_strength"), f.get("community_alignment"),
                f.get("transparency"),
                dim.evidence_maturity_level,
                psycopg2.extras.Json(dim.factors),
            ))

    conn.commit()
    cur.close()
    return str(assessment_id)
