"""Read-only inventory for Field Collector organization-ownership review.

The command reports aggregate counts and opaque, stable references only. It
does not infer tenant ownership from organization relationships or modify data.
"""

from __future__ import annotations

import argparse
import hashlib
from uuid import UUID

from services.common.cli import get_connection, print_json, run

_INVENTORY_SQL = """
WITH active_org_relationships AS (
    SELECT member.location_id,
           COUNT(*)::int AS active_relationship_count,
           COUNT(DISTINCT member.organization_id)::int AS active_org_count,
           COALESCE(
               ARRAY_AGG(
                   DISTINCT member.organization_id::text
                   ORDER BY member.organization_id::text
               )
                   FILTER (
                       WHERE member.membership_type = 'owned'
                         AND member.role = 'primary'
                   ),
               ARRAY[]::text[]
           ) AS owned_primary_org_ids
      FROM organization_member AS member
     WHERE member.status = 'active'
       AND (:location_id::uuid IS NULL OR member.location_id = :location_id::uuid)
     GROUP BY member.location_id
),
mobile_devices AS (
    SELECT device.location_id,
           COUNT(*)::int AS device_count,
           COUNT(*) FILTER (
               WHERE device.status = 'active' AND device.revoked_at IS NULL
           )::int AS active_device_count,
           COUNT(*) FILTER (
               WHERE device.tenant_organization_id IS NOT NULL
           )::int AS tenant_bound_device_count,
           COUNT(*) FILTER (
               WHERE device.tenant_organization_id IS NULL
           )::int AS tenant_unbound_device_count,
           COUNT(*) FILTER (
               WHERE device.status = 'active' AND device.revoked_at IS NULL
                 AND device.device_token_hash IS NOT NULL
                 AND device.tenant_organization_id IS NULL
           )::int AS active_unbound_token_device_count,
           COUNT(*) FILTER (
               WHERE device.tenant_organization_id IS NOT NULL
                 AND NOT EXISTS (
                     SELECT 1
                       FROM location AS loc
                       JOIN location_tenant_owner_verification AS owner
                         ON owner.location_id = loc.id
                        AND owner.organization_id = loc.organization_id
                        AND owner.revoked_at IS NULL
                       JOIN organization AS tenant
                         ON tenant.id = owner.organization_id
                        AND tenant.status = 'active'
                      WHERE loc.id = device.location_id
                        AND loc.status = 'active'
                        AND owner.organization_id = device.tenant_organization_id
                 )
           )::int AS owner_mismatch_device_count
      FROM mobile_device AS device
     WHERE device.location_id IS NOT NULL
       AND (:location_id::uuid IS NULL OR device.location_id = :location_id::uuid)
     GROUP BY device.location_id
),
mobile_enrollments AS (
    SELECT enrollment.location_id,
           COUNT(*)::int AS enrollment_count,
           COUNT(*) FILTER (
               WHERE enrollment.used_at IS NULL AND enrollment.revoked_at IS NULL
                 AND enrollment.expires_at > NOW()
           )::int AS pending_enrollment_count,
           COUNT(*) FILTER (
               WHERE enrollment.tenant_organization_id IS NOT NULL
           )::int AS tenant_bound_enrollment_count,
           COUNT(*) FILTER (
               WHERE enrollment.tenant_organization_id IS NULL
           )::int AS tenant_unbound_enrollment_count,
           COUNT(*) FILTER (
               WHERE enrollment.used_at IS NULL AND enrollment.revoked_at IS NULL
                 AND enrollment.expires_at > NOW()
                 AND enrollment.tenant_organization_id IS NULL
           )::int AS pending_unbound_enrollment_count,
           COUNT(*) FILTER (
               WHERE enrollment.tenant_organization_id IS NOT NULL
                 AND NOT EXISTS (
                     SELECT 1
                       FROM location AS loc
                       JOIN location_tenant_owner_verification AS owner
                         ON owner.location_id = loc.id
                        AND owner.organization_id = loc.organization_id
                        AND owner.revoked_at IS NULL
                       JOIN organization AS tenant
                         ON tenant.id = owner.organization_id
                        AND tenant.status = 'active'
                      WHERE loc.id = enrollment.location_id
                        AND loc.status = 'active'
                        AND owner.organization_id = enrollment.tenant_organization_id
                 )
           )::int AS owner_mismatch_enrollment_count
      FROM mobile_device_enrollment AS enrollment
     WHERE (:location_id::uuid IS NULL OR enrollment.location_id = :location_id::uuid)
     GROUP BY enrollment.location_id
),
mobile_collections AS (
    SELECT collection.location_id,
           COUNT(*)::int AS collection_count,
           COUNT(*) FILTER (
               WHERE COALESCE(eligibility.eligible_for_use, FALSE) = FALSE
           )::int AS ineligible_collection_count
      FROM offline_collection AS collection
      LEFT JOIN v_mobile_collection_use_eligibility AS eligibility
        ON eligibility.collection_id = collection.id
     WHERE collection.location_id IS NOT NULL
       AND (:location_id::uuid IS NULL OR collection.location_id = :location_id::uuid)
     GROUP BY collection.location_id
),
private_media AS (
    SELECT media.location_id,
           COUNT(*)::int AS media_upload_count,
           COUNT(*) FILTER (WHERE media.status = 'attached')::int AS attached_media_count
      FROM mobile_media_upload AS media
     WHERE (:location_id::uuid IS NULL OR media.location_id = :location_id::uuid)
     GROUP BY media.location_id
),
canonical_activity AS (
    SELECT activity.location_id,
           COUNT(*)::int AS canonical_activity_count
      FROM farm_activity AS activity
     WHERE activity.source_system = 'field_collector'
       AND (:location_id::uuid IS NULL OR activity.location_id = :location_id::uuid)
     GROUP BY activity.location_id
),
workflow_events AS (
    SELECT event.location_id, COUNT(*)::int AS workflow_event_count
      FROM farm_activity_workflow_event AS event
     WHERE (:location_id::uuid IS NULL OR event.location_id = :location_id::uuid)
     GROUP BY event.location_id
),
review_events AS (
    SELECT event.location_id, COUNT(*)::int AS review_event_count
      FROM mobile_collection_review_event AS event
     WHERE (:location_id::uuid IS NULL OR event.location_id = :location_id::uuid)
     GROUP BY event.location_id
),
report_snapshots AS (
    SELECT report.location_id, COUNT(*)::int AS report_snapshot_count
      FROM report_snapshot AS report
     WHERE report.location_id IS NOT NULL
       AND (:location_id::uuid IS NULL OR report.location_id = :location_id::uuid)
     GROUP BY report.location_id
),
dashboard_datasets AS (
    SELECT dataset.location_id, COUNT(*)::int AS dashboard_dataset_count
      FROM dashboard_dataset AS dataset
     WHERE dataset.location_id IS NOT NULL
       AND (:location_id::uuid IS NULL OR dataset.location_id = :location_id::uuid)
     GROUP BY dataset.location_id
)
SELECT location.id AS location_id,
       location.status AS location_status,
       location.organization_id AS assigned_organization_id,
       COALESCE(relationships.active_relationship_count, 0)
           AS active_organization_relationship_count,
       COALESCE(relationships.active_org_count, 0) AS active_organization_count,
       COALESCE(relationships.owned_primary_org_ids, ARRAY[]::text[])
           AS owned_primary_organization_ids,
       COALESCE(devices.device_count, 0) AS mobile_device_count,
       COALESCE(devices.active_device_count, 0) AS active_mobile_device_count,
       COALESCE(devices.tenant_bound_device_count, 0) AS tenant_bound_device_count,
       COALESCE(devices.tenant_unbound_device_count, 0) AS tenant_unbound_device_count,
       COALESCE(devices.active_unbound_token_device_count, 0)
           AS active_unbound_token_device_count,
       COALESCE(devices.owner_mismatch_device_count, 0) AS owner_mismatch_device_count,
       COALESCE(enrollments.enrollment_count, 0) AS enrollment_count,
       COALESCE(enrollments.pending_enrollment_count, 0) AS pending_enrollment_count,
       COALESCE(enrollments.tenant_bound_enrollment_count, 0)
           AS tenant_bound_enrollment_count,
       COALESCE(enrollments.tenant_unbound_enrollment_count, 0)
           AS tenant_unbound_enrollment_count,
       COALESCE(enrollments.pending_unbound_enrollment_count, 0)
           AS pending_unbound_enrollment_count,
       COALESCE(enrollments.owner_mismatch_enrollment_count, 0)
           AS owner_mismatch_enrollment_count,
       COALESCE(collections.collection_count, 0) AS mobile_collection_count,
       COALESCE(collections.ineligible_collection_count, 0)
           AS ineligible_mobile_collection_count,
       COALESCE(media.media_upload_count, 0) AS private_media_upload_count,
       COALESCE(media.attached_media_count, 0) AS attached_private_media_count,
       COALESCE(activity.canonical_activity_count, 0)
           AS canonical_field_activity_count,
       COALESCE(workflow.workflow_event_count, 0) AS workflow_event_count,
       COALESCE(review.review_event_count, 0) AS review_event_count,
       COALESCE(reports.report_snapshot_count, 0) AS report_snapshot_count,
       COALESCE(datasets.dashboard_dataset_count, 0) AS dashboard_dataset_count
  FROM location
  LEFT JOIN active_org_relationships AS relationships
    ON relationships.location_id = location.id
  LEFT JOIN mobile_devices AS devices ON devices.location_id = location.id
  LEFT JOIN mobile_enrollments AS enrollments ON enrollments.location_id = location.id
  LEFT JOIN mobile_collections AS collections ON collections.location_id = location.id
  LEFT JOIN private_media AS media ON media.location_id = location.id
  LEFT JOIN canonical_activity AS activity ON activity.location_id = location.id
  LEFT JOIN workflow_events AS workflow ON workflow.location_id = location.id
  LEFT JOIN review_events AS review ON review.location_id = location.id
  LEFT JOIN report_snapshots AS reports ON reports.location_id = location.id
  LEFT JOIN dashboard_datasets AS datasets ON datasets.location_id = location.id
 WHERE (:location_id::uuid IS NULL OR location.id = :location_id::uuid)
 ORDER BY location.id
"""

_UNLOCATED_SQL = """
SELECT (SELECT COUNT(*)::int FROM mobile_device WHERE location_id IS NULL)
           AS mobile_device_count,
       (SELECT COUNT(*)::int FROM mobile_device
         WHERE location_id IS NULL AND device_token_hash IS NOT NULL
           AND status = 'active' AND revoked_at IS NULL)
           AS active_unlocated_token_device_count,
       (SELECT COUNT(*)::int FROM mobile_device_enrollment
         WHERE location_id IS NULL AND tenant_organization_id IS NULL AND used_at IS NULL
           AND revoked_at IS NULL AND expires_at > NOW())
           AS pending_unlocated_unbound_enrollment_count,
       (SELECT COUNT(*)::int FROM offline_collection WHERE location_id IS NULL)
           AS mobile_collection_count,
       (SELECT COUNT(*)::int FROM report_snapshot WHERE location_id IS NULL)
           AS report_snapshot_count,
       (SELECT COUNT(*)::int FROM dashboard_dataset WHERE location_id IS NULL)
           AS dashboard_dataset_count
"""

_COUNT_FIELDS = (
    "mobile_device_count",
    "active_mobile_device_count",
    "enrollment_count",
    "pending_enrollment_count",
    "mobile_collection_count",
    "ineligible_mobile_collection_count",
    "private_media_upload_count",
    "attached_private_media_count",
    "canonical_field_activity_count",
    "workflow_event_count",
    "review_event_count",
    "report_snapshot_count",
    "dashboard_dataset_count",
)

_TENANT_BINDING_COUNT_FIELDS = (
    "tenant_bound_device_count",
    "tenant_unbound_device_count",
    "active_unbound_token_device_count",
    "owner_mismatch_device_count",
    "tenant_bound_enrollment_count",
    "tenant_unbound_enrollment_count",
    "pending_unbound_enrollment_count",
    "owner_mismatch_enrollment_count",
)

_REQUIRED_COLUMNS = (
    ("location", "id"),
    ("location", "status"),
    ("location", "organization_id"),
    ("organization_member", "location_id"),
    ("organization_member", "organization_id"),
    ("organization_member", "status"),
    ("organization_member", "membership_type"),
    ("organization_member", "role"),
    ("mobile_device", "location_id"),
    ("mobile_device", "device_token_hash"),
    ("mobile_device", "status"),
    ("mobile_device", "revoked_at"),
    ("mobile_device", "tenant_organization_id"),
    ("mobile_device_enrollment", "location_id"),
    ("mobile_device_enrollment", "tenant_organization_id"),
    ("mobile_device_enrollment", "used_at"),
    ("mobile_device_enrollment", "revoked_at"),
    ("mobile_device_enrollment", "expires_at"),
    ("location_tenant_owner_verification", "location_id"),
    ("location_tenant_owner_verification", "organization_id"),
    ("location_tenant_owner_verification", "revoked_at"),
    ("organization", "id"),
    ("organization", "status"),
    ("offline_collection", "id"),
    ("offline_collection", "location_id"),
    ("v_mobile_collection_use_eligibility", "collection_id"),
    ("v_mobile_collection_use_eligibility", "eligible_for_use"),
    ("mobile_media_upload", "location_id"),
    ("mobile_media_upload", "status"),
    ("farm_activity", "location_id"),
    ("farm_activity", "source_system"),
    ("farm_activity_workflow_event", "location_id"),
    ("mobile_collection_review_event", "location_id"),
    ("report_snapshot", "location_id"),
    ("dashboard_dataset", "location_id"),
)

_SCHEMA_COVERAGE_SQL = """
WITH required(relation_name, column_name) AS (
    VALUES
""" + ",\n".join(
    f"        ('{relation}', '{column}')" for relation, column in _REQUIRED_COLUMNS
) + """
), missing AS (
    SELECT required.relation_name, required.column_name
      FROM required
      LEFT JOIN information_schema.columns AS available
        ON available.table_schema = 'public'
       AND available.table_name = required.relation_name
       AND available.column_name = required.column_name
     WHERE available.column_name IS NULL
)
SELECT (SELECT COUNT(*)::int FROM required) AS required_column_count,
       COALESCE(
           ARRAY_AGG(relation_name || '.' || column_name ORDER BY relation_name, column_name),
           ARRAY[]::text[]
       ) AS missing_columns
  FROM missing
"""


def _schema_state(conn) -> tuple[dict, dict]:
    coverage = conn.execute(_SCHEMA_COVERAGE_SQL).first()
    if coverage is None:
        raise RuntimeError("schema coverage query returned no result")
    missing_columns = list(coverage["missing_columns"] or [])
    schema_coverage = {
        "status": "incomplete" if missing_columns else "complete",
        "required_column_count": coverage["required_column_count"],
        "available_column_count": coverage["required_column_count"] - len(missing_columns),
        "missing_columns": missing_columns,
    }

    migration_table_row = conn.execute(
        "SELECT to_regclass('public.schema_migration') IS NOT NULL AS present"
    ).first()
    migration_table_exists = bool(migration_table_row and migration_table_row["present"])
    applied_migration = None
    ordering_basis = "unavailable"
    if migration_table_exists:
        migration_id_column = conn.execute(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'schema_migration'
                   AND column_name = 'migration_id'
            ) AS present
            """
        ).first()
        if migration_id_column and migration_id_column["present"]:
            latest_migration = conn.execute(
                """
                SELECT migration_id
                  FROM schema_migration
                 WHERE status = 'applied'
                   AND left(migration_id, 7) = 'schema:'
                 ORDER BY
                    NULLIF(
                        substring(migration_id FROM '^schema:([0-9]+)_'), ''
                    )::numeric DESC NULLS LAST,
                    migration_id DESC
                 LIMIT 1
                """
            ).first()
            if latest_migration:
                applied_migration = latest_migration["migration_id"]
                ordering_basis = "schema_migration_id"

        if applied_migration is None:
            latest_numeric_version = conn.execute(
                """
                SELECT version
                  FROM schema_migration
                 WHERE status = 'applied'
                   AND version ~ '^[0-9]+$'
                 ORDER BY version::numeric DESC
                 LIMIT 1
                """
            ).first()
            if latest_numeric_version:
                applied_migration = latest_numeric_version["version"]
                ordering_basis = "numeric_version"
            else:
                latest_migration = conn.execute(
                    """
                    SELECT version
                      FROM schema_migration
                     WHERE status = 'applied'
                     ORDER BY applied_at DESC, version DESC
                     LIMIT 1
                    """
                ).first()
                applied_migration = latest_migration["version"] if latest_migration else None
                ordering_basis = "applied_at_fallback" if latest_migration else "unavailable"

    return schema_coverage, {
        "migration_history_available": bool(migration_table_exists),
        "latest_applied_migration": applied_migration,
        "migration_ordering_basis": ordering_basis,
    }


def _opaque_reference(value: object, entity: str) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(
        f"kokonut-tenant-preflight-v1:{entity}:{value}".encode("utf-8")
    ).hexdigest()[:16]


def _ownership_status(assigned_organization_id: object, candidate_ids: list[object]) -> str:
    assigned = str(assigned_organization_id) if assigned_organization_id is not None else None
    candidates = {str(value) for value in candidate_ids}
    if assigned is None:
        if len(candidates) > 1:
            return "unassigned_multiple_owner_candidates"
        if candidates:
            return "unassigned_owner_candidate_requires_review"
        return "unassigned"
    if len(candidates) > 1:
        return "multiple_owner_candidates"
    if not candidates:
        return "assigned_owner_not_confirmed_by_relationship"
    if assigned not in candidates:
        return "assigned_owner_mismatch"
    return "assigned_owner_matches_relationship"


def collect_inventory(location_id: str | None = None) -> dict:
    """Return aggregate owner and known-lineage counts without raw identifiers."""
    normalized_location_id = None
    if location_id is not None:
        try:
            normalized_location_id = str(UUID(location_id))
        except (TypeError, ValueError) as exc:
            raise ValueError("location_id must be a UUID") from exc

    with get_connection(connect_timeout=5) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '15s'")
        schema_coverage, schema_state = _schema_state(conn)
        if schema_coverage["status"] == "complete":
            rows = conn.execute(
                _INVENTORY_SQL,
                {"location_id": normalized_location_id},
            ).all()
            unlocated_rows = conn.execute(_UNLOCATED_SQL).all()

    if schema_coverage["status"] != "complete":
        return {
            "scope": "read_only_organization_ownership_and_known_lineage_preflight",
            "inventory_status": "schema_incomplete",
            "location_filter_applied": normalized_location_id is not None,
            "schema_coverage": schema_coverage,
            "schema_state": schema_state,
            "limitations": [
                "No ownership or lineage rows were queried because one or more "
                "required inventory columns are unavailable.",
                "Apply and verify the ordered migrations on an isolated copy "
                "before requesting a complete inventory.",
            ],
        }

    locations = []
    for row in rows:
        raw_candidate_ids = row["owned_primary_organization_ids"]
        if raw_candidate_ids is None:
            candidate_ids = []
        elif isinstance(raw_candidate_ids, (list, tuple)):
            candidate_ids = list(raw_candidate_ids)
        else:
            raise RuntimeError(
                "database driver returned an unsupported organization array representation"
            )
        status = _ownership_status(row["assigned_organization_id"], candidate_ids)
        locations.append(
            {
                "location_ref": _opaque_reference(row["location_id"], "location"),
                "location_status": row["location_status"],
                "assigned_organization_ref": _opaque_reference(
                    row["assigned_organization_id"], "organization"
                ),
                "owned_primary_organization_refs": sorted(
                    reference
                    for candidate_id in candidate_ids
                    if (
                        reference := _opaque_reference(candidate_id, "organization")
                    ) is not None
                ),
                "ownership_review_status": status,
                "active_organization_relationship_count": row[
                    "active_organization_relationship_count"
                ],
                "active_organization_count": row["active_organization_count"],
                "multiple_active_organization_relationships": (
                    row["active_organization_relationship_count"] > 1
                ),
                "records": {
                    field.removesuffix("_count"): row[field] for field in _COUNT_FIELDS
                },
                "mobile_tenant_binding": {
                    field.removesuffix("_count"): row[field]
                    for field in _TENANT_BINDING_COUNT_FIELDS
                },
            }
        )

    status_counts: dict[str, int] = {}
    for location in locations:
        status = location["ownership_review_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    totals = {
        field.removesuffix("_count"): sum(
            location["records"][field.removesuffix("_count")] for location in locations
        )
        for field in _COUNT_FIELDS
    }
    tenant_binding_totals = {
        field.removesuffix("_count"): sum(
            location["mobile_tenant_binding"][field.removesuffix("_count")]
            for location in locations
        )
        for field in _TENANT_BINDING_COUNT_FIELDS
    }
    unlocated = {
        "mobile_device": int(unlocated_rows[0]["mobile_device_count"]),
        "active_unlocated_token_device": int(
            unlocated_rows[0]["active_unlocated_token_device_count"]
        ),
        "pending_unlocated_unbound_enrollment": int(
            unlocated_rows[0]["pending_unlocated_unbound_enrollment_count"]
        ),
        "mobile_collection": int(unlocated_rows[0]["mobile_collection_count"]),
        "report_snapshot": int(unlocated_rows[0]["report_snapshot_count"]),
        "dashboard_dataset": int(unlocated_rows[0]["dashboard_dataset_count"]),
    }
    return {
        "scope": "read_only_organization_ownership_and_known_lineage_preflight",
        "inventory_status": "complete",
        "location_filter_applied": normalized_location_id is not None,
        "schema_coverage": schema_coverage,
        "schema_state": schema_state,
        "records_without_location_scope": "database_wide",
        "location_count": len(locations),
        "ownership_review_status_counts": dict(sorted(status_counts.items())),
        "locations_with_multiple_active_organization_relationships": sum(
            location["multiple_active_organization_relationships"] for location in locations
        ),
        "known_relation_rows_at_locations_without_direct_organization_assignment": sum(
            sum(location["records"].values())
            for location in locations
            if location["assigned_organization_ref"] is None
        ),
        "record_totals_by_known_relation": totals,
        "tenant_binding_totals_at_locations": tenant_binding_totals,
        "records_without_location": unlocated,
        "locations": locations,
        "limitations": [
            "Organization relationships are review evidence, not authorization "
            "or automatic owner assignment.",
            "Opaque references are stable only for this inventory format; no "
            "location or organization identifiers are returned.",
            "Counts cover listed direct relations only and do not prove complete "
            "downstream, export, or backup lineage.",
            "Relation row counts can include one collection in multiple lineage "
            "tables and are not a unique-record total.",
            "This report does not verify or enable row-level security.",
        ],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--location-id",
        help="optionally limit the inventory to one location UUID (the UUID is not emitted)",
    )
    args = parser.parse_args(argv)
    run(lambda: print_json(collect_inventory(args.location_id)))


if __name__ == "__main__":
    main()
