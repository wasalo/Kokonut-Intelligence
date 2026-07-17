"""Checks for the polymorphic relationship retirement registry."""

from pathlib import Path


SQL = Path("schemas/postgres/311_relationship_reference_policy.sql").read_text()


def test_polymorphic_relationships_have_explicit_policy_metadata():
    assert "CREATE TABLE IF NOT EXISTS relationship_reference_policy" in SQL
    assert "allowed_type_values TEXT[] NOT NULL" in SQL
    assert "replacement_target VARCHAR(150)" in SQL
    assert "owning_domain VARCHAR(80) NOT NULL" in SQL


def test_known_relationships_are_seeded_idempotently():
    assert "('party_relationship', 'scope_type', 'scope_id'" in SQL
    assert "('strategy_advantage_link', 'entity_type', 'entity_id'" in SQL
    assert "('strategy_evidence_link', 'source_type', 'source_id'" in SQL
    assert "ON CONFLICT (table_name, type_column, id_column) DO UPDATE SET" in SQL
