"""Focused guards for Phase 5 source-of-truth cleanup."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas/postgres"
SEED_DIR = ROOT / "schemas/seeds"


def test_raster_metadata_has_one_owner_and_explicit_compatibility_path():
    definitions = []
    for path in SCHEMA_DIR.glob("*.sql"):
        if re.search(r"CREATE TABLE IF NOT EXISTS raster_metadata\s*\(", path.read_text()):
            definitions.append(path.name)
    assert sorted(definitions) == ["059_drone_raster_integration.sql", "115_geospatial_enhancement.sql"]
    compatibility = (SCHEMA_DIR / "115_geospatial_enhancement.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS raster_metadata" in compatibility
    cleanup = (SCHEMA_DIR / "304_phase5_source_of_truth_cleanup.sql").read_text()
    assert "canonical 059 shape" in cleanup


def test_public_spatial_views_are_reconciled_once_and_registry_gated():
    cleanup = (SCHEMA_DIR / "304_phase5_source_of_truth_cleanup.sql").read_text()
    for view in ("v_public_spatial_clusters", "v_public_pest_hotspots", "v_public_canopy_analysis"):
        assert cleanup.count(f"CREATE OR REPLACE VIEW {view}") == 1
        assert "fr.status IN ('verified', 'published')" in cleanup


def test_directus_reconciliation_is_guarded_and_column_based():
    cleanup = (SCHEMA_DIR / "304_phase5_source_of_truth_cleanup.sql").read_text()
    assert "to_regclass('public.directus_fields')" in cleanup
    assert "information_schema.columns" in cleanup
    assert "SET fields = valid_fields" in cleanup


def test_agent_directus_permissions_use_current_schema_names():
    permissions = (ROOT / "config/directus/permissions.sql").read_text()
    cleanup = (SCHEMA_DIR / "305_directus_permission_field_cleanup.sql").read_text()
    for stale_field in ("agent_type", "capabilities", "input_data", "execution_result"):
        assert stale_field not in permissions
    assert "agent_name,agent_state,metadata,operator_wallet" in cleanup
    assert "task_type,inputs,subject_id,subject_type,requested_by" in cleanup
