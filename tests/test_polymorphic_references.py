"""Named polymorphic-reference governance checks for Phase 3."""

from pathlib import Path


POLICY_SQL = Path("schemas/postgres/311_relationship_reference_policy.sql").read_text()
VALIDATION_SQL = Path("schemas/postgres/313_phase2_backfill_phase3_reference_validation.sql").read_text()


def test_polymorphic_reference_policy_has_retirement_metadata():
    assert "relationship_reference_policy" in POLICY_SQL
    assert "replacement_target" in POLICY_SQL
    assert "enforcement_status" in POLICY_SQL


def test_high_risk_polymorphic_links_have_database_validation():
    assert "validate_party_scope_reference" in VALIDATION_SQL
    assert "validate_strategy_advantage_link_target" in VALIDATION_SQL
    assert "DEFERRABLE INITIALLY IMMEDIATE" in VALIDATION_SQL
