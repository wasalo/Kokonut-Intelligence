"""Source contracts for Field Collector's current-use eligibility gate."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
MIGRATION = ROOT / "schemas/postgres/386_farm_activity_consent_use_gate.sql"
DIRECTUS_PERMISSIONS = ROOT / "config/directus/permissions.sql"


def test_migration_fails_closed_on_current_source_form_and_consent_state():
    sql = MIGRATION.read_text()

    for fragment in (
        "RETURNS BOOLEAN",
        "activity_source_system IS DISTINCT FROM 'field_collector'",
        "activity_source_raw->>'offline_collection_id' IS DISTINCT FROM activity_source_id",
        "collection.location_id = activity_location_id",
        "collection.form_validation_status = 'active'",
        "collection.form_review_required = FALSE",
        "revision.status = 'active'",
        "eligibility.eligible_for_use IS TRUE",
    ):
        assert fragment in sql


def test_migration_retires_linked_collections_and_freezes_mobile_provenance():
    sql = MIGRATION.read_text()

    assert "trg_queue_collections_for_inactive_form_revision" in sql
    assert "form_validation_status = 'retired_review'" in sql
    assert "trg_guard_farm_activity_use_eligibility" in sql
    assert "provenance_changed := ROW(" in sql
    assert "Field Collector farm activity source provenance is immutable" in sql


def test_migration_preserves_directus_for_legacy_data_and_routes_mobile_reads_to_gateway():
    sql = MIGRATION.read_text()

    assert "to_regclass('public.directus_permissions') IS NOT NULL" in sql
    assert "collection = 'farm_activity'" in sql
    assert "action = 'read'" in sql
    assert '"source_system":{"_null":true}' in sql
    assert '"source_system":{"_neq":"field_collector"}' in sql
    assert "COALESCE(permissions, '{}'::JSON)" in sql
    assert "jsonb_path_exists(" in sql
    assert "scoped Gateway review/use endpoints" in sql

    directus_seed = DIRECTUS_PERMISSIONS.read_text()
    assert '"source_system":{"_null":true}' in directus_seed
    assert '"source_system":{"_neq":"field_collector"}' in directus_seed
    assert "jsonb_path_exists(" in directus_seed
    assert "action = 'read'" in directus_seed


def test_dashboard_dataset_rewrite_is_limited_to_known_seeded_queries():
    sql = MIGRATION.read_text()

    assert "AND query_sql = $old$" in sql
    assert "fa.status = 'published'" in sql
    assert "farm_activity_source_eligible_for_use(" in sql
