"""Regression coverage for canonical consent event integrity."""

from pathlib import Path

from conftest import assert_sql_contains


MIGRATION = Path("schemas/postgres/322_consent_append_only.sql")
SEED = Path("schemas/seeds/105_stakeholder_vocabulary.sql")


def test_canonical_consent_is_append_only() -> None:
    assert_sql_contains(
        MIGRATION,
        "BEFORE UPDATE OR DELETE ON stakeholder_consent",
        "stakeholder_consent is append-only",
    )


def test_backdated_consent_requires_system_migration() -> None:
    assert_sql_contains(
        MIGRATION,
        "NEW.effective_at < NEW.created_at",
        "NEW.consent_method <> 'system_migration'",
    )


def test_canonical_seed_does_not_update_consent_history() -> None:
    assert_sql_contains(SEED, "ON CONFLICT (id) DO NOTHING")
