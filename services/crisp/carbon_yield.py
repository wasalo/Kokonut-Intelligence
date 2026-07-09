"""Carbon yield risk scoring module.

Adapted from SW-CRISP Annexure 1.  Estimates the likelihood of meeting
carbon/biomass yield targets using scenario modeling across tree inventory,
soil carbon, harvest data, and remote sensing observations.

Scoring approach:
1. Query tree inventory, soil carbon, harvest events, and NDVI
2. Build three scenarios: minimum (conservative), realistic (moderate), optimistic (liberal)
3. Compute yield likelihood as ratio of ex-ante estimate against scenarios
4. Convert likelihood to risk score (higher likelihood = lower risk)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras

from .models import DimensionScore
from .normalization import clamp_risk_score, likelihood_to_risk_score


# Carbon pool default fractions (IPCC 2006)
CARBON_FRACTION = 0.47
CO2E_CONVERSION = 3.67
BELOW_GROUND_RATIO = 0.25
SOC_DEFAULT_RATE = 0.5  # tonnes C/ha/yr for coastal wetlands (IPCC default)


def _query_tree_summary(conn, location_id: str) -> Dict[str, Any]:
    """Aggregate tree inventory carbon for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS tree_count,
            COALESCE(SUM(biomass_estimate_kg), 0) AS total_biomass_kg,
            COALESCE(SUM(carbon_estimate_tonnes), 0) AS total_carbon_tonnes,
            COALESCE(SUM(co2e_estimate_tonnes), 0) AS total_co2e_tonnes,
            COALESCE(AVG(avg_dbh_cm), 0) AS avg_dbh_cm,
            MIN(allometric_source) AS allometric_source
        FROM tree_inventory
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_soil_carbon(conn, location_id: str) -> Dict[str, Any]:
    """Get latest soil carbon measurement."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            carbon_tonnes_per_ha,
            carbon_pct,
            is_baseline,
            measurement_date
        FROM soil_carbon_measurement
        WHERE location_id = %s
        ORDER BY measurement_date DESC NULLS LAST
        LIMIT 1
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_harvest_summary(conn, location_id: str) -> Dict[str, Any]:
    """Aggregate harvest data for yield estimation."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS harvest_count,
            COALESCE(SUM(estimated_yield_kg), 0) AS total_yield_kg,
            COALESCE(AVG(estimated_yield_kg), 0) AS avg_yield_kg,
            MIN(harvest_date) AS first_harvest,
            MAX(harvest_date) AS last_harvest
        FROM harvest_event he
        JOIN crop_cycle cc ON cc.id = he.crop_cycle_id
        WHERE cc.location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_ndvi_latest(conn, location_id: str) -> Optional[float]:
    """Get latest NDVI value for pre-project vegetation density."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT ndvi
        FROM remote_sensing_observation
        WHERE location_id = %s AND ndvi IS NOT NULL
        ORDER BY observation_date DESC NULLS LAST
        LIMIT 1
    """, (location_id,))
    row = cur.fetchone()
    cur.close()
    return float(row["ndvi"]) if row and row["ndvi"] is not None else None


def _query_carbon_benchmark(conn, species: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get carbon benchmark for a tree species."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if species:
        cur.execute("""
            SELECT species, benchmark_co2e_per_ha, benchmark_biomass_kg_per_ha
            FROM carbon_benchmark
            WHERE LOWER(species) = LOWER(%s)
            LIMIT 1
        """, (species,))
    else:
        cur.execute("""
            SELECT species, benchmark_co2e_per_ha, benchmark_biomass_kg_per_ha
            FROM carbon_benchmark
            ORDER BY benchmark_co2e_per_ha DESC
            LIMIT 1
        """)
    row = dict(cur.fetchone() or {})
    cur.close()
    return row if row else None


def _build_scenarios(
    tree_summary: Dict[str, Any],
    soil_carbon: Dict[str, Any],
    benchmark: Optional[Dict[str, Any]],
    planting_density: Optional[float],
    mortality_rate: Optional[float],
) -> Dict[str, float]:
    """Build three carbon yield scenarios from available data.

    Uses tree inventory actuals as the base, adjusted by benchmark ratios
    and mortality assumptions.
    """
    base_co2e = float(tree_summary.get("total_co2e_tonnes", 0) or 0)
    soil_c = float(soil_carbon.get("carbon_tonnes_per_ha", 0) or 0)

    # If no trees yet, use benchmark estimate
    if base_co2e == 0 and benchmark:
        bench_co2e = float(benchmark.get("benchmark_co2e_per_ha", 0) or 0)
        density = planting_density or 1000
        base_co2e = bench_co2e * (density / 1000)

    # Mortality adjustment
    mortality = (mortality_rate or 10.0) / 100.0

    # Conservative (minimum): 60% of base, full mortality, no SOC
    minimum = base_co2e * 0.60 * (1 - mortality)

    # Realistic: 85% of base, partial mortality, SOC included
    realistic = base_co2e * 0.85 * (1 - mortality * 0.5) + soil_c * 0.5

    # Optimistic: 100% of base, low mortality, SOC + growth bonus
    optimistic = base_co2e * 1.0 * (1 - mortality * 0.2) + soil_c * 1.0

    return {
        "minimum": max(0, minimum),
        "realistic": max(0, realistic),
        "optimistic": max(0, optimistic),
    }


def _compute_yield_likelihood(
    ex_ante: float,
    scenarios: Dict[str, float],
) -> float:
    """Compute yield likelihood based on where ex-ante falls among scenarios.

    Returns 0-1 where:
    - 1.0 = extremely likely (ex_ante <= minimum scenario)
    - 0.75 = quite likely (ex_ante between minimum and realistic)
    - 0.5 = neutral (ex_ante between realistic and optimistic)
    - 0.25 = unlikely (ex_ante at optimistic)
    - 0.0 = extremely unlikely (ex_ante > optimistic)
    """
    minimum = scenarios["minimum"]
    realistic = scenarios["realistic"]
    optimistic = scenarios["optimistic"]

    if optimistic <= 0:
        return 0.5  # No data, neutral

    if ex_ante <= minimum:
        return 1.0
    elif ex_ante <= realistic:
        # Linear interpolation between 1.0 and 0.75
        if realistic <= minimum:
            return 0.75
        ratio = (ex_ante - minimum) / (realistic - minimum)
        return 1.0 - ratio * 0.25
    elif ex_ante <= optimistic:
        # Linear interpolation between 0.75 and 0.25
        if optimistic <= realistic:
            return 0.25
        ratio = (ex_ante - realistic) / (optimistic - realistic)
        return 0.75 - ratio * 0.50
    else:
        return 0.0


def compute_carbon_yield_risk(
    conn,
    location_id: str,
    ex_ante_estimate: Optional[float] = None,
    planting_density: Optional[float] = None,
    mortality_rate: Optional[float] = None,
) -> DimensionScore:
    """Compute carbon yield risk score for a location.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.
        ex_ante_estimate: Expected carbon yield (tonnes CO2e). If None, uses benchmark.
        planting_density: Trees per hectare. If None, uses 1000 default.
        mortality_rate: Expected mortality percentage (0-100). If None, uses 10% default.

    Returns:
        DimensionScore with risk_score 0-100 (higher = more risk).
    """
    tree_summary = _query_tree_summary(conn, location_id)
    soil_carbon = _query_soil_carbon(conn, location_id)
    harvest_summary = _query_harvest_summary(conn, location_id)
    ndvi = _query_ndvi_latest(conn, location_id)
    benchmark = _query_carbon_benchmark(conn)

    # Default ex-ante from tree inventory if not provided
    if ex_ante_estimate is None:
        ex_ante_estimate = float(tree_summary.get("total_co2e_tonnes", 0) or 0)
    if ex_ante_estimate == 0 and benchmark:
        ex_ante_estimate = float(benchmark.get("benchmark_co2e_per_ha", 0) or 0)

    scenarios = _build_scenarios(
        tree_summary, soil_carbon, benchmark, planting_density, mortality_rate
    )
    likelihood = _compute_yield_likelihood(ex_ante_estimate, scenarios)
    risk_score = likelihood_to_risk_score(likelihood)

    # Uncertainty estimation from scenario spread
    if scenarios["optimistic"] > 0:
        uncertainty_pct = ((scenarios["optimistic"] - scenarios["minimum"]) / scenarios["optimistic"]) * 100
    else:
        uncertainty_pct = 50.0  # High uncertainty when no data

    # Evidence maturity: more data = higher maturity
    evidence_level = 1
    if float(tree_summary.get("tree_count", 0) or 0) > 0:
        evidence_level = 3
    if float(tree_summary.get("tree_count", 0) or 0) > 10:
        evidence_level = 4
    if ndvi is not None:
        evidence_level = min(evidence_level + 1, 6)
    if float(soil_carbon.get("carbon_tonnes_per_ha", 0) or 0) > 0:
        evidence_level = min(evidence_level + 1, 6)

    # Confidence from evidence maturity
    from .config import CONFIDENCE_THRESHOLDS
    confidence = CONFIDENCE_THRESHOLDS.get(evidence_level, "insufficient_evidence")

    # Build factor details
    factors = {
        "tree_count": int(tree_summary.get("tree_count", 0) or 0),
        "total_biomass_kg": float(tree_summary.get("total_biomass_kg", 0) or 0),
        "total_co2e_tonnes": float(tree_summary.get("total_co2e_tonnes", 0) or 0),
        "soil_carbon_tonnes_per_ha": float(soil_carbon.get("carbon_tonnes_per_ha", 0) or 0),
        "ndvi": ndvi,
        "allometric_source": tree_summary.get("allometric_source"),
        "scenario_minimum": scenarios["minimum"],
        "scenario_realistic": scenarios["realistic"],
        "scenario_optimistic": scenarios["optimistic"],
        "ex_ante_estimate": ex_ante_estimate,
        "mortality_rate_pct": mortality_rate or 10.0,
        "planting_density_per_ha": planting_density or 1000,
    }

    return DimensionScore(
        dimension_key="carbon_yield",
        dimension_name="Carbon Yield Risk",
        risk_score=clamp_risk_score(risk_score),
        confidence_level=confidence,
        evidence_maturity_level=evidence_level,
        weight=0.0,  # Set by scoring engine
        factors=factors,
        evidence_summary=f"Yield likelihood {likelihood:.2f} across 3 scenarios (min={scenarios['minimum']:.2f}, real={scenarios['realistic']:.2f}, opt={scenarios['optimistic']:.2f})",
        uncertainty_notes=f"Scenario spread: {uncertainty_pct:.1f}%" if uncertainty_pct > 30 else None,
    )
