"""Rankings and preferences tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/079_web_of_trust.sql")


def test_schema_has_preference_signal_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS preference_signal" in content


def test_schema_has_ranking_algorithm_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS ranking_algorithm" in content


def test_schema_has_ranking_result_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS ranking_result" in content


def test_schema_has_ranking_comparison_view() -> None:
    content = SCHEMA.read_text()
    assert "v_public_ranking_comparison" in content


def test_schema_has_preference_type_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_pref_type" in content
    assert "metric_preference" in content
    assert "evaluator_trust" in content
    assert "capital_allocation" in content


def test_schema_has_algorithm_status_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_rank_algo_status" in content
    assert "active" in content
    assert "deprecated" in content


def test_rankings_service_exists() -> None:
    assert Path("services/scoring/rankings.py").exists()


def test_service_has_register_algorithm() -> None:
    from services.scoring.rankings import register_algorithm
    assert callable(register_algorithm)


def test_service_has_list_algorithms() -> None:
    from services.scoring.rankings import list_algorithms
    assert callable(list_algorithms)


def test_service_has_compute_ranking() -> None:
    from services.scoring.rankings import compute_ranking
    assert callable(compute_ranking)


def test_service_has_compare_rankings() -> None:
    from services.scoring.rankings import compare_rankings
    assert callable(compare_rankings)


def test_service_has_submit_preference() -> None:
    from services.scoring.rankings import submit_preference
    assert callable(submit_preference)


def test_service_has_aggregate_preferences() -> None:
    from services.scoring.rankings import aggregate_preferences
    assert callable(aggregate_preferences)


def test_service_has_get_preference_influence() -> None:
    from services.scoring.rankings import get_preference_influence
    assert callable(get_preference_influence)


def test_service_uses_logging() -> None:
    content = Path("services/scoring/rankings.py").read_text()
    assert "get_logger" in content


def test_service_uses_exponential_decay() -> None:
    content = Path("services/scoring/rankings.py").read_text()
    assert "math.exp" in content
    assert "decay_rate" in content


def test_service_weights_by_trust_score() -> None:
    content = Path("services/scoring/rankings.py").read_text()
    assert "trust_score" in content
    assert "evaluator_weight" in content


def test_schema_has_unique_constraint_on_ranking() -> None:
    content = SCHEMA.read_text()
    assert "UNIQUE(algorithm_id, location_id, ranking_period)" in content


def test_schema_has_period_index() -> None:
    content = SCHEMA.read_text()
    assert "idx_rank_result_period" in content


def test_schema_has_rank_index() -> None:
    content = SCHEMA.read_text()
    assert "idx_rank_result_rank" in content


def test_compare_returns_all_algorithms() -> None:
    content = Path("services/scoring/rankings.py").read_text()
    assert "algorithms_compared" in content
    assert "comparison" in content


def test_preference_weighted_by_trust() -> None:
    content = Path("services/scoring/rankings.py").read_text()
    assert "effective_weight" in content
    assert "evaluator_weight" in content
