"""Source-level checks for explicit associative entities."""

from pathlib import Path


SQL = Path("schemas/postgres/309_relationship_entities.sql").read_text()


def test_relationship_entities_have_parent_keys_and_semantic_uniqueness():
    for table in (
        "farmer_crop",
        "metric_value_source",
        "cooperative_board_member",
        "forecast_assumption",
        "role_permission",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SQL
    assert "UNIQUE (farmer_id, crop_id, season_key)" in SQL
    assert "REFERENCES metric_value(id) ON DELETE CASCADE" in SQL
    assert "REFERENCES cooperative_membership(id) ON DELETE RESTRICT" in SQL
    assert "REFERENCES role_assignment(id) ON DELETE CASCADE" in SQL


def test_relationship_entities_keep_provenance_and_temporal_attributes():
    assert "evidence_maturity INTEGER" in SQL
    assert "source_ref TEXT" in SQL
    assert "valid_from DATE" in SQL
    assert "term_start DATE NOT NULL" in SQL
