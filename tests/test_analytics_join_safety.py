"""Checks for fan-trap-safe stakeholder analytics."""

from pathlib import Path


SQL = Path("schemas/postgres/316_stakeholder_analytics_safety.sql").read_text()


def test_stakeholder_landscape_preaggregates_each_child_relationship():
    assert "WITH identifier_counts AS" in SQL
    assert "relationship_counts AS" in SQL
    assert "interest_counts AS" in SQL
    assert "FROM party_relationship" in SQL
    assert "FROM stakeholder_interest" in SQL
    assert "ssa.is_current = TRUE" in SQL


def test_stakeholder_landscape_does_not_fan_join_raw_child_tables():
    assert "LEFT JOIN party_relationship" not in SQL
    assert "LEFT JOIN stakeholder_interest" not in SQL
