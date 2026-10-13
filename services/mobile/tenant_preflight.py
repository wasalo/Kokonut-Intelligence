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
               ARRAY_AGG(DISTINCT member.organization_id ORDER BY member.organization_id)
                   FILTER (
                       WHERE member.membership_type = 'owned'
                         AND member.role = 'primary'
                   ),
               ARRAY[]::uuid[]
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
           )::int AS active_device_count
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
           )::int AS pending_enrollment_count
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
       COALESCE(relationships.owned_primary_org_ids, ARRAY[]::uuid[])
           AS owned_primary_organization_ids,
       COALESCE(devices.device_count, 0) AS mobile_device_count,
       COALESCE(devices.active_device_count, 0) AS active_mobile_device_count,
       COALESCE(enrollments.enrollment_count, 0) AS enrollment_count,
       COALESCE(enrollments.pending_enrollment_count, 0) AS pending_enrollment_count,
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
        rows = conn.execute(
            _INVENTORY_SQL,
            {"location_id": normalized_location_id},
        ).all()
        unlocated_rows = conn.execute(_UNLOCATED_SQL).all()

    locations = []
    for row in rows:
        candidate_ids = list(row["owned_primary_organization_ids"] or [])
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
    unlocated = {
        "mobile_device": int(unlocated_rows[0]["mobile_device_count"]),
        "mobile_collection": int(unlocated_rows[0]["mobile_collection_count"]),
        "report_snapshot": int(unlocated_rows[0]["report_snapshot_count"]),
        "dashboard_dataset": int(unlocated_rows[0]["dashboard_dataset_count"]),
    }
    return {
        "scope": "read_only_organization_ownership_and_known_lineage_preflight",
        "location_filter_applied": normalized_location_id is not None,
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
