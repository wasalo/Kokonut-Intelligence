"""EBF schema migration tests."""

from pathlib import Path


P0_SCHEMA = Path("schemas/postgres/032_ebf_scorecard.sql")
P1_SCHEMA = Path("schemas/postgres/033_ebf_p1_operations.sql")


def test_all_ebf_tables_are_declared() -> None:
    text = (P0_SCHEMA.read_text() + P1_SCHEMA.read_text()).lower()
    for table in [
        "ebf_pillar", "ebf_rubric_band", "ebf_scorecard", "ebf_score", "ebf_score_evidence",
        "ebf_farm_metric_profile", "ebf_calibration_session", "ebf_calibration_decision",
        "ebf_trust_graph_node", "ebf_trust_graph_edge", "ebf_improvement_recommendation",
    ]:
        assert f"create table if not exists {table}" in text


def test_ebf_score_links_to_impact_claim() -> None:
    text = P0_SCHEMA.read_text().lower()
    assert "impact_claim_id uuid references impact_claim" in text
    assert "idx_ebf_score_impact_claim" in text


if __name__ == "__main__":
    test_all_ebf_tables_are_declared()
    test_ebf_score_links_to_impact_claim()
