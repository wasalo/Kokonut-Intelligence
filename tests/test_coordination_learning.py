"""Coordination learning-link coverage."""

from pathlib import Path


def test_learning_links_cover_required_domains():
    schema = (Path(__file__).resolve().parents[1] / "schemas/postgres/237_coordination_learning_accounting.sql").read_text()
    for link_type in ("capability_maturity", "process_improvement", "technology_alternative", "training", "insight_transfer", "stakeholder_outcome"):
        assert f"'{link_type}'" in schema


def test_metric_observations_are_explicit_and_reviewable():
    schema = (Path(__file__).resolve().parents[1] / "schemas/postgres/237_coordination_learning_accounting.sql").read_text()
    assert "methodology TEXT NOT NULL" in schema
    assert "status <> 'verified' OR verified_by_party_id IS NOT NULL" in schema
    assert "never ownership or reputation" in schema
