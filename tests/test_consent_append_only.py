"""Regression coverage for canonical consent event integrity."""

from pathlib import Path


MIGRATION = Path("schemas/postgres/322_consent_append_only.sql")
SEED = Path("schemas/seeds/105_stakeholder_vocabulary.sql")


def test_canonical_consent_is_append_only() -> None:
    text = MIGRATION.read_text()
    assert "BEFORE UPDATE OR DELETE ON stakeholder_consent" in text
    assert "stakeholder_consent is append-only" in text


def test_backdated_consent_requires_system_migration() -> None:
    text = MIGRATION.read_text()
    assert "NEW.effective_at < NEW.created_at" in text
    assert "NEW.consent_method <> 'system_migration'" in text


def test_canonical_seed_does_not_update_consent_history() -> None:
    text = SEED.read_text()
    assert "ON CONFLICT (id) DO NOTHING" in text
