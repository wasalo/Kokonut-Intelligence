"""EBF pillar scoring tests."""

from services.scoring.calculators import (
    compute_air_quality_score,
    compute_biodiversity_score,
    compute_carbon_sequestration_score,
    compute_equity_community_score,
    compute_implementation_quality_score,
    compute_soil_health_score,
    compute_water_management_score,
)
from services.scoring.implementation_quality import compute_implementation_quality_score as compute_implementation_quality_score_wrapper


def test_pillar_calculators_return_0_to_10_scores() -> None:
    scores = [
        compute_air_quality_score(2500),
        compute_water_management_score(50),
        compute_soil_health_score(3),
        compute_biodiversity_score(50),
        compute_carbon_sequestration_score(10, 1),
        compute_equity_community_score(80, 20),
        compute_implementation_quality_score(75),
    ]
    assert all(0 <= score <= 10 for score in scores)
    assert scores[0] == 5.0
    assert scores[-1] == 7.5
    assert compute_implementation_quality_score_wrapper(80) == 8.0


def test_carbon_calculator_requires_positive_area() -> None:
    try:
        compute_carbon_sequestration_score(10, 0)
    except ValueError as exc:
        assert "farm_area_ha" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_soil_health_score_scales_correctly() -> None:
    low = compute_soil_health_score(-2)
    high = compute_soil_health_score(8)
    assert low == 0.0
    assert high == 10.0


def test_equity_score_averages_worker_and_training() -> None:
    score = compute_equity_community_score(100, 40)
    assert score == 10.0
    score_zero = compute_equity_community_score(0, 0)
    assert score_zero == 0.0


def test_biodiversity_score_normalizes_richness() -> None:
    assert compute_biodiversity_score(0) == 0.0
    assert compute_biodiversity_score(100) == 10.0
    assert compute_biodiversity_score(50) == 5.0


if __name__ == "__main__":
    test_pillar_calculators_return_0_to_10_scores()
    test_carbon_calculator_requires_positive_area()
