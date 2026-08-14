"""Named evidence-lineage checks for the Phase 2 normalized provenance path."""

from pathlib import Path

from conftest import assert_sql_contains


NORMALIZATION_SQL = Path("schemas/postgres/313_phase2_backfill_phase3_reference_validation.sql").read_text()


def test_metric_provenance_backfill_is_ordered_and_idempotent():
    assert_sql_contains(
        Path("schemas/postgres/313_phase2_backfill_phase3_reference_validation.sql"),
        "WITH ORDINALITY",
        "metric_value_source",
        "ON CONFLICT (metric_value_id, source_entity_type, source_entity_id, source_ref) DO NOTHING",
    )


def test_provenance_compatibility_view_is_explicit():
    assert_sql_contains(
        Path("schemas/postgres/313_phase2_backfill_phase3_reference_validation.sql"),
        "CREATE OR REPLACE VIEW v_metric_value_provenance",
        "mvs.sequence_order",
    )
