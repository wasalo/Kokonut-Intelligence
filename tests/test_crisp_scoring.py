"""CRISP risk scoring tests.

Tests cover:
- Normalization helpers (0-100 risk scores)
- Yield likelihood computation
- Hazard score conversion
- Weighted average risk
- Rating band assignment
- Composite rating construction
- Climate hazard scoring functions
- Policy risk sub-factor scoring
- Financial risk sub-factor scoring
- Implementation risk sub-factor scoring
"""

from pathlib import Path

from services.crisp.config import CRISP_VERSION, DEFAULT_WEIGHTS, RATING_BANDS
from services.crisp.models import CompositeRating, DimensionScore
from services.crisp.normalization import (
    clamp_risk_score,
    hazard_score_to_risk,
    likelihood_to_risk_score,
    normalize_to_risk,
    weighted_average_risk,
)

SCHEMA = Path("schemas/postgres/076_crisp_risk_scoring.sql")


# ---------------------------------------------------------------------------
# Normalization tests
# ---------------------------------------------------------------------------

def test_clamp_risk_score_within_bounds() -> None:
    assert clamp_risk_score(50.0) == 50.0
    assert clamp_risk_score(0.0) == 0.0
    assert clamp_risk_score(100.0) == 100.0


def test_clamp_risk_score_below_bounds() -> None:
    assert clamp_risk_score(-10.0) == 0.0
    assert clamp_risk_score(-100.0) == 0.0


def test_clamp_risk_score_above_bounds() -> None:
    assert clamp_risk_score(150.0) == 100.0
    assert clamp_risk_score(999.0) == 100.0


def test_clamp_risk_score_rounding() -> None:
    assert clamp_risk_score(33.333) == 33.33
    assert clamp_risk_score(66.666) == 66.67


def test_normalize_to_risk_basic() -> None:
    # Midpoint should give 50
    result = normalize_to_risk(5.0, 0, 10)
    assert result == 50.0


def test_normalize_to_risk_low_value() -> None:
    result = normalize_to_risk(0.0, 0, 10)
    assert result == 0.0


def test_normalize_to_risk_high_value() -> None:
    result = normalize_to_risk(10.0, 0, 10)
    assert result == 100.0


def test_normalize_to_risk_inverted() -> None:
    # Inverted: high raw value = low risk
    result = normalize_to_risk(10.0, 0, 10, invert=True)
    assert result == 0.0
    result = normalize_to_risk(0.0, 0, 10, invert=True)
    assert result == 100.0


def test_normalize_to_risk_invalid_range() -> None:
    try:
        normalize_to_risk(5.0, 10, 0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_likelihood_to_risk_score_extremely_likely() -> None:
    # Likelihood 1.0 (extremely likely to yield) = 0 risk
    assert likelihood_to_risk_score(1.0) == 0.0


def test_likelihood_to_risk_score_extremely_unlikely() -> None:
    # Likelihood 0.0 (extremely unlikely) = 100 risk
    assert likelihood_to_risk_score(0.0) == 100.0


def test_likelihood_to_risk_score_neutral() -> None:
    # Likelihood 0.5 = 50 risk
    assert likelihood_to_risk_score(0.5) == 50.0


def test_hazard_score_to_risk_zero() -> None:
    assert hazard_score_to_risk(0.0, 15.0) == 0.0


def test_hazard_score_to_risk_max() -> None:
    assert hazard_score_to_risk(15.0, 15.0) == 100.0


def test_hazard_score_to_risk_midpoint() -> None:
    assert hazard_score_to_risk(7.5, 15.0) == 50.0


def test_hazard_score_to_risk_invalid_max() -> None:
    try:
        hazard_score_to_risk(5.0, 0.0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_weighted_average_risk_basic() -> None:
    scores = {"a": 100.0, "b": 0.0}
    weights = {"a": 0.5, "b": 0.5}
    result = weighted_average_risk(scores, weights)
    assert result == 50.0


def test_weighted_average_risk_all_weight_on_high() -> None:
    scores = {"a": 100.0, "b": 0.0}
    weights = {"a": 1.0, "b": 0.0}
    result = weighted_average_risk(scores, weights)
    assert result == 100.0


def test_weighted_average_risk_all_weight_on_low() -> None:
    scores = {"a": 100.0, "b": 0.0}
    weights = {"a": 0.0, "b": 1.0}
    result = weighted_average_risk(scores, weights)
    assert result == 0.0


def test_weighted_average_risk_none_scores_excluded() -> None:
    scores = {"a": 100.0, "b": None}
    weights = {"a": 0.5, "b": 0.5}
    result = weighted_average_risk(scores, weights)
    # Only "a" contributes, so result = 100
    assert result == 100.0


def test_weighted_average_risk_empty() -> None:
    result = weighted_average_risk({}, {})
    assert result == 0.0


def test_weighted_average_risk_default_weights() -> None:
    # Use CRISP default weights
    scores = {
        "carbon_yield": 30.0,
        "climate": 60.0,
        "policy": 20.0,
        "financial": 40.0,
        "implementation": 50.0,
    }
    result = weighted_average_risk(scores, DEFAULT_WEIGHTS)
    expected = (
        30.0 * 0.40 + 60.0 * 0.25 + 20.0 * 0.15 + 40.0 * 0.10 + 50.0 * 0.10
    )
    assert abs(result - expected) < 0.01


# ---------------------------------------------------------------------------
# Rating band tests
# ---------------------------------------------------------------------------

def test_rating_band_aaa() -> None:
    for score in [91, 95, 100]:
        for rating, (low, high) in RATING_BANDS.items():
            if low <= score <= high:
                if score >= 91:
                    assert rating == "AAA"


def test_rating_band_d() -> None:
    for score in [0, 10, 19]:
        for rating, (low, high) in RATING_BANDS.items():
            if low <= score <= high:
                if score <= 20:
                    assert rating == "D"


def test_all_bands_cover_full_range() -> None:
    covered = set()
    for rating, (low, high) in RATING_BANDS.items():
        for score in range(low, high + 1):
            covered.add(score)
    assert 0 in covered
    assert 100 in covered
    assert len(covered) == 101


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

def test_default_weights_sum_to_one() -> None:
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


def test_default_weights_all_positive() -> None:
    for key, weight in DEFAULT_WEIGHTS.items():
        assert weight > 0, f"Weight for {key} must be positive"


def test_crisp_version_format() -> None:
    # Should be like "v2026.07"
    assert CRISP_VERSION.startswith("v")
    parts = CRISP_VERSION[1:].split(".")
    assert len(parts) == 2
    assert len(parts[0]) == 4  # Year
    assert len(parts[1]) == 2  # Month


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

def test_dimension_score_creation() -> None:
    ds = DimensionScore(
        dimension_key="carbon_yield",
        dimension_name="Carbon Yield Risk",
        risk_score=45.0,
        confidence_level="moderate",
        evidence_maturity_level=4,
        weight=0.40,
    )
    assert ds.dimension_key == "carbon_yield"
    assert ds.risk_score == 45.0
    assert ds.weight == 0.40


def test_composite_rating_to_dict() -> None:
    cr = CompositeRating(
        location_id="test-loc",
        period_start="2025-01-01",
        period_end="2025-12-31",
        carbon_yield_score=30.0,
        climate_score=60.0,
        policy_score=20.0,
        financial_score=40.0,
        implementation_score=50.0,
        composite_score=38.5,
        rating="B",
        confidence_level="moderate",
        methodology_version="v2026.07",
        weights=DEFAULT_WEIGHTS,
    )
    d = cr.to_dict()
    assert d["location_id"] == "test-loc"
    assert d["rating"] == "B"
    assert d["composite_score"] == 38.5
    assert "dimensions" in d


def test_composite_rating_with_dimensions() -> None:
    dims = [
        DimensionScore("carbon_yield", "Carbon Yield Risk", 30.0, "moderate", 4, 0.40),
        DimensionScore("climate", "Climate Risk", 60.0, "low", 2, 0.25),
    ]
    cr = CompositeRating(
        location_id="test-loc",
        period_start="2025-01-01",
        period_end="2025-12-31",
        dimensions=dims,
    )
    d = cr.to_dict()
    assert len(d["dimensions"]) == 2
    assert d["dimensions"][0]["dimension_key"] == "carbon_yield"


# ---------------------------------------------------------------------------
# Carbon yield scenario tests (unit logic only)
# ---------------------------------------------------------------------------

def test_build_scenarios_no_trees() -> None:
    from services.crisp.carbon_yield import _build_scenarios
    tree_summary = {"total_co2e_tonnes": 0, "tree_count": 0}
    soil_carbon = {"carbon_tonnes_per_ha": 0}
    scenarios = _build_scenarios(tree_summary, soil_carbon, None, None, None)
    assert scenarios["minimum"] >= 0
    assert scenarios["realistic"] >= scenarios["minimum"]
    assert scenarios["optimistic"] >= scenarios["realistic"]


def test_build_scenarios_with_trees() -> None:
    from services.crisp.carbon_yield import _build_scenarios
    tree_summary = {"total_co2e_tonnes": 100, "tree_count": 50}
    soil_carbon = {"carbon_tonnes_per_ha": 10}
    scenarios = _build_scenarios(tree_summary, soil_carbon, None, 1000, 10.0)
    assert scenarios["minimum"] < scenarios["realistic"]
    assert scenarios["realistic"] < scenarios["optimistic"]
    assert scenarios["minimum"] > 0


def test_compute_yield_likelihood_at_minimum() -> None:
    from services.crisp.carbon_yield import _compute_yield_likelihood
    scenarios = {"minimum": 50, "realistic": 80, "optimistic": 100}
    likelihood = _compute_yield_likelihood(50, scenarios)
    assert likelihood == 1.0


def test_compute_yield_likelihood_at_realistic() -> None:
    from services.crisp.carbon_yield import _compute_yield_likelihood
    scenarios = {"minimum": 50, "realistic": 80, "optimistic": 100}
    likelihood = _compute_yield_likelihood(80, scenarios)
    assert abs(likelihood - 0.75) < 0.01


def test_compute_yield_likelihood_at_optimistic() -> None:
    from services.crisp.carbon_yield import _compute_yield_likelihood
    scenarios = {"minimum": 50, "realistic": 80, "optimistic": 100}
    likelihood = _compute_yield_likelihood(100, scenarios)
    assert abs(likelihood - 0.25) < 0.01


def test_compute_yield_likelihood_beyond_optimistic() -> None:
    from services.crisp.carbon_yield import _compute_yield_likelihood
    scenarios = {"minimum": 50, "realistic": 80, "optimistic": 100}
    likelihood = _compute_yield_likelihood(150, scenarios)
    assert likelihood == 0.0


def test_compute_yield_likelihood_zero_optimistic() -> None:
    from services.crisp.carbon_yield import _compute_yield_likelihood
    scenarios = {"minimum": 0, "realistic": 0, "optimistic": 0}
    likelihood = _compute_yield_likelihood(50, scenarios)
    assert likelihood == 0.5  # Neutral when no data


# ---------------------------------------------------------------------------
# Climate hazard scoring tests (unit logic only)
# ---------------------------------------------------------------------------

def test_score_drought_no_data() -> None:
    from services.crisp.climate_risk import _score_drought
    weather = {"observation_count": 0, "dry_days": 0, "avg_rainfall": 100}
    score = _score_drought(weather, [])
    assert 0.0 <= score <= 3.0


def test_score_drought_high_risk() -> None:
    from services.crisp.climate_risk import _score_drought
    weather = {"observation_count": 100, "dry_days": 80, "avg_rainfall": 20}
    incidents = [{"incident_type": "drought", "severity": "critical", "incident_count": 2}]
    score = _score_drought(weather, incidents)
    assert score >= 2.0


def test_score_flood_no_data() -> None:
    from services.crisp.climate_risk import _score_flood
    weather = {"avg_rainfall": 50}
    score = _score_flood(weather, [])
    assert 0.0 <= score <= 3.0


def test_score_heatwave_high_temp() -> None:
    from services.crisp.climate_risk import _score_heatwave
    weather = {"max_temp": 48}
    score = _score_heatwave(weather, [])
    assert score >= 2.0


def test_score_fire_dry_hot() -> None:
    from services.crisp.climate_risk import _score_fire
    weather = {"dry_days": 80, "observation_count": 100, "max_temp": 40}
    score = _score_fire(weather, [])
    assert score >= 1.5


def test_score_storm_high_wind() -> None:
    from services.crisp.climate_risk import _score_storm
    weather = {"max_wind": 120}
    score = _score_storm(weather, [])
    assert score >= 2.0


def test_score_water_stress_arid() -> None:
    from services.crisp.climate_risk import _score_water_stress
    weather = {"avg_rainfall": 20, "avg_humidity": 30}
    score = _score_water_stress(weather, [])
    assert score >= 2.0


# ---------------------------------------------------------------------------
# Policy risk sub-factor tests (unit logic only)
# ---------------------------------------------------------------------------

def test_score_national_policy_certified() -> None:
    from services.crisp.policy_risk import _score_national_policy
    assert _score_national_policy({"status": "certified"}) == 1.0


def test_score_national_policy_none() -> None:
    from services.crisp.policy_risk import _score_national_policy
    assert _score_national_policy({}) == 0.0


def test_score_carbon_rights_owned() -> None:
    from services.crisp.policy_risk import _score_carbon_rights
    assert _score_carbon_rights({"stewardship_model": "community_owned"}) == 1.0


def test_score_land_tenure_low_risk() -> None:
    from services.crisp.policy_risk import _score_land_tenure
    assert _score_land_tenure({"landlord_dependency_risk": "low"}) == 1.0


def test_score_land_tenure_critical_risk() -> None:
    from services.crisp.policy_risk import _score_land_tenure
    assert _score_land_tenure({"landlord_dependency_risk": "critical"}) == 0.1


def test_score_community_alignment_high_coverage() -> None:
    from services.crisp.policy_risk import _score_community_alignment
    governance = {"representation_coverage_pct": 90, "marginalized_voice_count": 5}
    feedback = {"avg_satisfaction": 8.0}
    score = _score_community_alignment(governance, feedback)
    assert score >= 0.7


def test_score_certification_risk_no_barriers() -> None:
    from services.crisp.policy_risk import _score_certification_risk
    assert _score_certification_risk([]) == 0.25


def test_score_certification_risk_critical() -> None:
    from services.crisp.policy_risk import _score_certification_risk
    barriers = [{"severity": "critical", "mitigation_plan": None}]
    score = _score_certification_risk(barriers)
    assert score == 1.0


# ---------------------------------------------------------------------------
# Financial risk sub-factor tests (unit logic only)
# ---------------------------------------------------------------------------

def test_compute_liquidity_risk_low_runway() -> None:
    from services.crisp.financial_risk import _compute_liquidity_risk
    assert _compute_liquidity_risk({"runway_months": 2}) >= 0.8


def test_compute_liquidity_risk_high_runway() -> None:
    from services.crisp.financial_risk import _compute_liquidity_risk
    assert _compute_liquidity_risk({"runway_months": 36}) <= 0.2


def test_compute_revenue_risk_high_grant_dependency() -> None:
    from services.crisp.financial_risk import _compute_revenue_risk
    sustainability = {"grant_dependency_pct": 90, "revenue_streams": ["grant"]}
    revenue = {"total_revenue": 10000, "revenue_stddev": 0, "revenue_count": 5}
    score = _compute_revenue_risk(revenue, sustainability)
    assert score >= 0.6


def test_compute_cost_risk_long_payback() -> None:
    from services.crisp.financial_risk import _compute_cost_risk
    expense = {"total_expense": 50000, "labor_cost": 20000, "input_cost": 15000}
    unit_economics = {"payback_months": 60}
    score = _compute_cost_risk(expense, unit_economics)
    assert score >= 0.5


# ---------------------------------------------------------------------------
# Implementation risk sub-factor tests (unit logic only)
# ---------------------------------------------------------------------------

def test_score_track_record_high_readiness() -> None:
    from services.crisp.implementation_risk import _score_track_record
    onboarding = {"readiness_score": 9}
    practices = {"total_principles": 5, "adopted_principles": 5, "avg_practice_score": 4.5}
    score = _score_track_record(onboarding, practices)
    assert score >= 0.8


def test_score_track_record_low_readiness() -> None:
    from services.crisp.implementation_risk import _score_track_record
    onboarding = {"readiness_score": 2}
    practices = {"total_principles": 5, "adopted_principles": 1, "avg_practice_score": 1.0}
    score = _score_track_record(onboarding, practices)
    assert score <= 0.4


def test_score_team_strength_with_training() -> None:
    from services.crisp.implementation_risk import _score_team_strength
    onboarding = {"training_completed_pct": 80, "community_engagement_level": "high"}
    training = {"training_count": 10}
    score = _score_team_strength(onboarding, training)
    assert score >= 0.7


def test_score_network_strength() -> None:
    from services.crisp.implementation_risk import _score_network_strength
    onboarding = {"implementation_partners_count": 5, "infrastructure_readiness": "ready"}
    score = _score_network_strength(onboarding)
    assert score >= 0.8


def test_score_transparency() -> None:
    from services.crisp.implementation_risk import _score_transparency
    governance = {"representation_coverage_pct": 85, "decision_method": "consensus"}
    feedback = {"feedback_count": 10, "published_count": 8}
    score = _score_transparency(governance, feedback)
    assert score >= 0.7


# ---------------------------------------------------------------------------
# Schema file exists
# ---------------------------------------------------------------------------

def test_schema_file_exists() -> None:
    assert SCHEMA.exists(), f"Schema file not found: {SCHEMA}"


def test_schema_contains_tables() -> None:
    content = SCHEMA.read_text()
    expected_tables = [
        "crisp_risk_dimension",
        "crisp_location_weight",
        "crisp_risk_assessment",
        "crisp_carbon_yield_risk",
        "crisp_climate_risk",
        "crisp_policy_risk",
        "crisp_financial_risk",
        "crisp_implementation_risk",
    ]
    for table in expected_tables:
        assert table in content, f"Table {table} not found in schema"


def test_schema_contains_views() -> None:
    content = SCHEMA.read_text()
    assert "v_crisp_composite_rating" in content
    assert "v_crisp_latest_assessment" in content
