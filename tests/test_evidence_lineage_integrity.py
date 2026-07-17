"""Named evidence-lineage checks for the Phase 2 normalized provenance path."""

from pathlib import Path


NORMALIZATION_SQL = Path("schemas/postgres/313_phase2_backfill_phase3_reference_validation.sql").read_text()


def test_metric_provenance_backfill_is_ordered_and_idempotent():
    assert "WITH ORDINALITY" in NORMALIZATION_SQL
    assert "metric_value_source" in NORMALIZATION_SQL
    assert "ON CONFLICT (metric_value_id, source_entity_type, source_entity_id, source_ref) DO NOTHING" in NORMALIZATION_SQL


def test_provenance_compatibility_view_is_explicit():
    assert "CREATE OR REPLACE VIEW v_metric_value_provenance" in NORMALIZATION_SQL
    assert "mvs.sequence_order" in NORMALIZATION_SQL
