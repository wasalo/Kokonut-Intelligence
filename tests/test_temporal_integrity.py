"""Checks for Phase 4 temporal and current-state semantics."""

from pathlib import Path


SQL = Path("schemas/postgres/315_temporal_semantics.sql").read_text()


def test_temporal_entities_have_validity_and_supersession_fields():
    assert "role_assignment" in SQL and "supersedes_id UUID REFERENCES role_assignment" in SQL
    assert "data_sharing_consent" in SQL and "supersedes_id UUID REFERENCES data_sharing_consent" in SQL
    assert "party_relationship" in SQL and "supersedes_id UUID REFERENCES party_relationship" in SQL
    assert "is_current BOOLEAN NOT NULL DEFAULT TRUE" in SQL


def test_temporal_exclusion_constraints_cover_active_relationships():
    assert "ex_role_assignment_active_interval" in SQL
    assert "ex_consent_active_interval" in SQL
    assert "ex_party_relationship_active_interval" in SQL
    assert "tstzrange" in SQL
    assert "daterange" in SQL


def test_location_baseline_has_history_and_current_view():
    assert "CREATE TABLE IF NOT EXISTS location_baseline" in SQL
    assert "supersedes_id UUID REFERENCES location_baseline" in SQL
    assert "v_current_location_baseline" in SQL
