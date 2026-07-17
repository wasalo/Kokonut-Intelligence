"""Focused checks for Phase 2 normalization and Phase 3 reference validation."""

from pathlib import Path


SQL = Path("schemas/postgres/313_phase2_backfill_phase3_reference_validation.sql").read_text()


def test_phase2_backfills_relationship_shaped_sources_and_exposes_views():
    assert "unnest(mv.source_record_ids)" in SQL
    assert "jsonb_array_elements" in SQL
    assert "farmer_crop" in SQL
    assert "v_metric_value_provenance" in SQL
    assert "v_role_assignment_permissions" in SQL


def test_phase3_validates_stakeholder_scopes_and_strategy_targets():
    assert "validate_party_scope_reference" in SQL
    assert "trg_party_relationship_scope_reference" in SQL
    assert "trg_stakeholder_interest_scope_reference" in SQL
    assert "validate_strategy_advantage_link_target" in SQL
    assert "trg_strategy_advantage_link_target" in SQL
    assert "FROM business_capability" in SQL
