"""
Fortune 500 Calculator — Core Scoring Engine

Calculates composite scores from financial, ecological, and
governance data. Produces a 0-1000 ranking score.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json
import uuid
import psycopg2
import psycopg2.extras

from ..ingestion.base import get_db


# Scoring weights
WEIGHTS = {
    "financial": 0.45,
    "ecological": 0.25,
    "governance": 0.15,
    "growth": 0.15,
}

# Regional benchmarks (East Africa smallholder)
BENCHMARKS = {
    "revenue_per_ha_usd": 1500,
    "noi_margin_pct": 25,
    "loss_rate_pct": 10,
    "ndvi": 0.55,
    "soil_organic_matter_pct": 2.5,
    "data_completeness_pct": 70,
}


@dataclass
class FarmMetrics:
    """Input metrics for scoring."""
    location_id: str
    location_name: str = ""

    # Financial
    total_revenue_usd: float = 0
    total_costs_usd: float = 0
    noi_usd: float = 0
    revenue_per_ha_usd: float = 0
    operating_margin_pct: float = 0
    loss_rate_pct: float = 0
    total_capex_usd: float = 0

    # Ecological
    avg_ndvi: float = 0
    soil_organic_matter_pct: float = 0
    ecological_score: float = 0
    carbon_sequestration_tonnes: float = 0
    carbon_credit_value_usd: float = 0

    # Governance
    total_activities: int = 0
    verified_activities: int = 0
    attestation_count: int = 0
    data_completeness_pct: float = 0

    # Growth
    revenue_growth_pct: float = 0
    yield_growth_pct: float = 0
    projected_revenue_growth_pct: float = 0
    area_ha: float = 0

    # Infrastructure & Planning (new)
    water_access_score: float = 0  # avg reliability * quality from water_access
    capital_source_count: int = 0
    digital_lego_count: int = 0
    attestation_plan_count: int = 0
    attestation_plan_active: int = 0


@dataclass
class ScoreResult:
    """Scoring result."""
    financial_score: float = 0
    ecological_score: float = 0
    governance_score: float = 0
    growth_score: float = 0
    composite_score: float = 0
    rank: int = 0
    percentile: float = 0
    tier: str = ""
    breakdown: Dict[str, Any] = field(default_factory=dict)


def get_farm_metrics(location_id: str) -> FarmMetrics:
    """Collect all metrics for a farm from the database."""
    db = get_db()
    metrics = FarmMetrics(location_id=location_id)

    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Location info
        cur.execute("SELECT name, latitude, longitude FROM location WHERE id = %s", (location_id,))
        loc = cur.fetchone()
        if loc:
            metrics.location_name = loc["name"]

        # Financial metrics
        cur.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as revenue,
                   COALESCE(SUM(return_amount + discount_amount), 0) as returns,
                   COUNT(*) as sale_count
            FROM sales_event
            WHERE location_id = %s AND status IN ('verified', 'published')
        """, (location_id,))
        fin = cur.fetchone()
        if fin:
            metrics.total_revenue_usd = float(fin["revenue"])
            metrics.loss_rate_pct = (float(fin["returns"]) / max(float(fin["revenue"]), 1)) * 100

        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as costs
            FROM expense_event
            WHERE location_id = %s AND status IN ('verified', 'published')
        """, (location_id,))
        cost_row = cur.fetchone()
        if cost_row:
            metrics.total_costs_usd = float(cost_row["costs"])

        metrics.noi_usd = metrics.total_revenue_usd - metrics.total_costs_usd
        metrics.operating_margin_pct = (
            (metrics.noi_usd / metrics.total_revenue_usd * 100)
            if metrics.total_revenue_usd > 0 else 0
        )

        # Area
        cur.execute("""
            SELECT COALESCE(SUM(p.area), 0) as total_area
            FROM plot p
            JOIN farm f ON p.farm_id = f.id
            WHERE f.location_id = %s
        """, (location_id,))
        area_row = cur.fetchone()
        if area_row:
            metrics.area_ha = float(area_row["total_area"])
        metrics.revenue_per_ha_usd = (
            metrics.total_revenue_usd / metrics.area_ha
            if metrics.area_ha > 0 else 0
        )

        # Ecological metrics
        cur.execute("""
            SELECT AVG(ndvi) as avg_ndvi, AVG(canopy_cover_pct) as avg_canopy
            FROM remote_sensing_observation
            WHERE location_id = %s
        """, (location_id,))
        eco = cur.fetchone()
        if eco:
            metrics.avg_ndvi = float(eco["avg_ndvi"] or 0.5)

        cur.execute("""
            SELECT AVG(organic_matter_pct) as som
            FROM soil_sample WHERE location_id = %s
        """, (location_id,))
        soil = cur.fetchone()
        if soil and soil["som"]:
            metrics.soil_organic_matter_pct = float(soil["som"])

        # Governance metrics
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN status IN ('verified', 'published') THEN 1 END) as verified
            FROM farm_activity WHERE location_id = %s
        """, (location_id,))
        gov = cur.fetchone()
        if gov:
            metrics.total_activities = gov["total"]
            metrics.verified_activities = gov["verified"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM attestation_record
            WHERE subject_id = %s OR subject_type = 'location'
        """, (location_id,))
        att = cur.fetchone()
        if att:
            metrics.attestation_count = att["cnt"]

        # Data completeness (how many expected data types are present)
        data_points = 0
        total_points = 6
        for tbl in ["harvest_event", "sales_event", "expense_event",
                     "weather_observation", "remote_sensing_observation", "sensor_reading"]:
            cur.execute(f"SELECT COUNT(*) as cnt FROM {tbl} WHERE location_id = %s", (location_id,))
            if cur.fetchone()["cnt"] > 0:
                data_points += 1
        metrics.data_completeness_pct = (data_points / total_points) * 100

        # Ecological score from forecast engine
        cur.execute("""
            SELECT value FROM forecast_output
            WHERE location_id = %s AND metric_name = 'ecological_score_forecast'
            ORDER BY calculated_at DESC LIMIT 1
        """, (location_id,))
        eco_score = cur.fetchone()
        if eco_score and eco_score["value"]:
            metrics.ecological_score = float(eco_score["value"])

        # Growth signal from revenue multiplier opportunity
        cur.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as revenue
            FROM sales_event
            WHERE location_id = %s AND status IN ('verified', 'published')
              AND sale_date >= NOW() - INTERVAL '365 days'
        """, (location_id,))
        recent_rev = cur.fetchone()
        recent_revenue = float(recent_rev["revenue"]) if recent_rev else 0

        cur.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as revenue
            FROM sales_event
            WHERE location_id = %s AND status IN ('verified', 'published')
              AND sale_date >= NOW() - INTERVAL '730 days'
              AND sale_date < NOW() - INTERVAL '365 days'
        """, (location_id,))
        prev_rev = cur.fetchone()
        prev_revenue = float(prev_rev["revenue"]) if prev_rev else 0

        if prev_revenue > 0:
            metrics.revenue_growth_pct = ((recent_revenue - prev_revenue) / prev_revenue) * 100

        # Yield growth
        cur.execute("""
            SELECT AVG(actual_yield) as current_yield
            FROM crop_cycle
            WHERE location_id = %s AND status = 'completed'
              AND actual_harvest_date >= NOW() - INTERVAL '365 days'
        """, (location_id,))
        cur_yield = cur.fetchone()
        cur.execute("""
            SELECT AVG(actual_yield) as prev_yield
            FROM crop_cycle
            WHERE location_id = %s AND status = 'completed'
              AND actual_harvest_date >= NOW() - INTERVAL '730 days'
              AND actual_harvest_date < NOW() - INTERVAL '365 days'
        """, (location_id,))
        prev_yield = cur.fetchone()
        if cur_yield and prev_yield and prev_yield["prev_yield"] and cur_yield["current_yield"]:
            metrics.yield_growth_pct = (
                (float(cur_yield["current_yield"]) - float(prev_yield["prev_yield"]))
                / float(prev_yield["prev_yield"]) * 100
            )

        # Forecast-projected revenue growth (from forecast engine)
        cur.execute("""
            SELECT value, inputs
            FROM forecast_output
            WHERE location_id = %s AND metric_name = 'projected_revenue_usd'
            ORDER BY calculated_at DESC LIMIT 1
        """, (location_id,))
        proj_rev = cur.fetchone()
        if proj_rev and proj_rev["value"] and metrics.total_revenue_usd > 0:
            projected_revenue = float(proj_rev["value"])
            metrics.projected_revenue_growth_pct = (
                (projected_revenue - metrics.total_revenue_usd) / metrics.total_revenue_usd * 100
            )

        # Carbon sequestration and credit value from forecast engine
        cur.execute("""
            SELECT metric_name, value
            FROM forecast_output
            WHERE location_id = %s AND metric_name IN ('carbon_sequestration_tonnes', 'carbon_credit_value_usd')
            ORDER BY calculated_at DESC LIMIT 2
        """, (location_id,))
        for row in cur.fetchall():
            if row["metric_name"] == "carbon_sequestration_tonnes":
                metrics.carbon_sequestration_tonnes = float(row["value"])
            elif row["metric_name"] == "carbon_credit_value_usd":
                metrics.carbon_credit_value_usd = float(row["value"])

        # Water access score (avg of reliability * quality across sources)
        cur.execute("""
            SELECT AVG(reliability_score * COALESCE(quality_score, 50) / 100) as avg_score
            FROM water_access
            WHERE location_id = %s AND status = 'active'
        """, (location_id,))
        water = cur.fetchone()
        if water and water["avg_score"]:
            metrics.water_access_score = float(water["avg_score"])

        # Capital sources
        cur.execute("SELECT COUNT(*) as cnt FROM capital_source WHERE status = 'active'")
        cs = cur.fetchone()
        metrics.capital_source_count = cs["cnt"] if cs else 0

        # Digital Lego usage
        cur.execute("""
            SELECT COUNT(DISTINCT protocol_id) as cnt
            FROM digital_lego_usage
            WHERE location_id = %s
        """, (location_id,))
        dl = cur.fetchone()
        metrics.digital_lego_count = dl["cnt"] if dl else 0

        # Attestation plan
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN status IN ('in_progress', 'achieved') THEN 1 END) as active
            FROM attestation_plan
            WHERE location_id = %s
        """, (location_id,))
        ap = cur.fetchone()
        if ap:
            metrics.attestation_plan_count = ap["total"]
            metrics.attestation_plan_active = ap["active"]

        # Total capex from capex_breakdown
        cur.execute("""
            SELECT COALESCE(SUM(amount_usd), 0) as total_capex
            FROM capex_breakdown
            WHERE location_id = %s AND status IN ('verified', 'published')
        """, (location_id,))
        capex = cur.fetchone()
        if capex:
            metrics.total_capex_usd = float(capex["total_capex"])

    db.close()
    return metrics


def score_financial(m: FarmMetrics) -> float:
    """Score financial performance (0-1000)."""
    scores = []

    # Revenue per hectare vs benchmark
    rev_score = min(100, (m.revenue_per_ha_usd / BENCHMARKS["revenue_per_ha_usd"]) * 100)
    scores.append(rev_score)

    # Operating margin vs benchmark
    margin_score = min(100, max(0, (m.operating_margin_pct / BENCHMARKS["noi_margin_pct"]) * 100))
    scores.append(margin_score)

    # Loss rate (inverted — lower is better)
    loss_score = min(100, max(0, (1 - m.loss_rate_pct / 50) * 100))
    scores.append(loss_score)

    # Carbon credit value as revenue supplement
    if m.carbon_credit_value_usd > 0:
        carbon_score = min(100, (m.carbon_credit_value_usd / max(m.total_revenue_usd, 1)) * 100)
        scores.append(carbon_score)

    return sum(scores) / len(scores) * 10 if scores else 0


def score_ecological(m: FarmMetrics) -> float:
    """Score ecological performance (0-1000)."""
    scores = []

    # NDVI vs benchmark
    ndvi_score = min(100, (m.avg_ndvi / BENCHMARKS["ndvi"]) * 100) if m.avg_ndvi > 0 else 50
    scores.append(ndvi_score)

    # Soil organic matter
    som_score = min(100, (m.soil_organic_matter_pct / BENCHMARKS["soil_organic_matter_pct"]) * 100) if m.soil_organic_matter_pct > 0 else 50
    scores.append(som_score)

    # Ecological score from forecast engine (if available)
    if m.ecological_score > 0:
        scores.append(min(100, m.ecological_score))

    # Carbon sequestration (bonus: positive tonnes = positive signal)
    if m.carbon_sequestration_tonnes > 0:
        carbon_eco_score = min(100, m.carbon_sequestration_tonnes * 10)
        scores.append(carbon_eco_score)

    # Water access quality (0-100 scale)
    if m.water_access_score > 0:
        scores.append(min(100, m.water_access_score))

    return sum(scores) / len(scores) * 10 if scores else 500


def score_governance(m: FarmMetrics) -> float:
    """Score governance and data quality (0-1000)."""
    scores = []

    # Verification rate
    if m.total_activities > 0:
        verify_rate = m.verified_activities / m.total_activities
        scores.append(verify_rate * 100)
    else:
        scores.append(50)

    # Attestation count (more is better, up to a point)
    att_score = min(100, m.attestation_count * 20)
    scores.append(att_score)

    # Data completeness
    scores.append(m.data_completeness_pct)

    # Attestation plan maturity (planned + in_progress + achieved)
    if m.attestation_plan_count > 0:
        plan_maturity = (m.attestation_plan_active / m.attestation_plan_count) * 100
        scores.append(min(100, plan_maturity))

    # Digital Lego adoption
    if m.digital_lego_count > 0:
        lego_score = min(100, m.digital_lego_count * 20)
        scores.append(lego_score)

    return sum(scores) / len(scores) * 10 if scores else 500


def score_growth(m: FarmMetrics) -> float:
    """Score growth trajectory (0-1000)."""
    scores = []

    # Revenue growth: 50/50 blend of historical YoY and forecast-projected
    if m.projected_revenue_growth_pct != 0:
        blended_revenue_growth = (m.revenue_growth_pct * 0.5) + (m.projected_revenue_growth_pct * 0.5)
    else:
        blended_revenue_growth = m.revenue_growth_pct

    if blended_revenue_growth > 0:
        scores.append(min(100, blended_revenue_growth * 5))
    else:
        scores.append(50)

    # Yield growth
    if m.yield_growth_pct > 0:
        scores.append(min(100, m.yield_growth_pct * 5))
    else:
        scores.append(50)

    # Activity volume (proxy for operational maturity)
    activity_score = min(100, m.total_activities * 3)
    scores.append(activity_score)

    return sum(scores) / len(scores) * 10 if scores else 500


def calculate_score(metrics: FarmMetrics) -> ScoreResult:
    """Calculate composite Fortune 500 score."""
    fin = score_financial(metrics)
    eco = score_ecological(metrics)
    gov = score_governance(metrics)
    grw = score_growth(metrics)

    composite = (
        fin * WEIGHTS["financial"]
        + eco * WEIGHTS["ecological"]
        + gov * WEIGHTS["governance"]
        + grw * WEIGHTS["growth"]
    )

    # Determine tier
    if composite >= 800:
        tier = "Platinum"
    elif composite >= 600:
        tier = "Gold"
    elif composite >= 400:
        tier = "Silver"
    elif composite >= 200:
        tier = "Bronze"
    else:
        tier = "Developing"

    return ScoreResult(
        financial_score=round(fin, 1),
        ecological_score=round(eco, 1),
        governance_score=round(gov, 1),
        growth_score=round(grw, 1),
        composite_score=round(composite, 1),
        tier=tier,
        breakdown={
            "weights": WEIGHTS,
            "benchmarks": BENCHMARKS,
            "inputs": {
                "revenue_per_ha": metrics.revenue_per_ha_usd,
                "operating_margin_pct": metrics.operating_margin_pct,
                "loss_rate_pct": metrics.loss_rate_pct,
                "avg_ndvi": metrics.avg_ndvi,
                "soil_organic_matter_pct": metrics.soil_organic_matter_pct,
                "data_completeness_pct": metrics.data_completeness_pct,
                "attestation_count": metrics.attestation_count,
            },
        },
    )


def rank_farms(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank farms by composite score and assign percentiles."""
    sorted_results = sorted(results, key=lambda x: x["composite_score"], reverse=True)
    n = len(sorted_results)
    for i, r in enumerate(sorted_results):
        r["rank"] = i + 1
        r["percentile"] = round((1 - i / max(n, 1)) * 100, 1)
    return sorted_results


def calculate_all_farms() -> List[Dict[str, Any]]:
    """Calculate scores for all farms."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT f.location_id, l.name
            FROM farm f
            JOIN location l ON f.location_id = l.id
        """)
        farms = cur.fetchall()
    db.close()

    results = []
    for farm in farms:
        location_id = str(farm[0])
        metrics = get_farm_metrics(location_id)
        score = calculate_score(metrics)
        results.append({
            "location_id": location_id,
            "location_name": metrics.location_name,
            "financial_score": score.financial_score,
            "ecological_score": score.ecological_score,
            "governance_score": score.governance_score,
            "growth_score": score.growth_score,
            "composite_score": score.composite_score,
            "tier": score.tier,
            "breakdown": score.breakdown,
        })

    return rank_farms(results)
