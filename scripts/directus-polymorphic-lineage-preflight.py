#!/usr/bin/env python3
"""Aggregate-only preflight for Directus polymorphic workflow/audit rows.

Set DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN to an explicitly selected read-only
database target. The DSN is never printed and no database is selected by
default. Only aggregate counts leave PostgreSQL.
"""

from __future__ import annotations

import json
import os
from typing import Any

import psycopg2

# This allowlist is intentionally explicit. Direct-location mappings are
# limited to collections with a source-schema `location_id` column. The one
# non-direct mapping follows the protocol bridge's declared intent -> mapping
# -> location relationship. Unknown collection values are never returned.
DIRECT_LOCATION_SOURCES = (
    "farm_activity",
    "harvest_event",
    "expense_event",
    "sales_event",
    "loss_event",
    "labor_event",
    "field_note",
    "forecast_scenario",
    "report_snapshot",
    "dashboard_dataset",
    "farm_registry_record",
    "inventory_event",
    "maintenance_event",
    "revenue_event",
    "stakeholder_outcome",
    "stakeholder_feedback",
    "credit_batch",
    "project_credit_class_enrollment",
    "retirement_certificate",
    "metric_proposal",
    "mrv_claim",
    "metric_value",
    # These lifecycle collections have explicit direct location columns but
    # are not yet in the current Directus tenant-scoped hook registry.
    "impact_claim",
    "mrv_event",
)

CUSTOM_SOURCE_SQL = {
    "protocol_execution_intent": """
        SELECT 'protocol_execution_intent'::text AS source_collection,
               intent.id AS source_id,
               mapping.location_id AS location_id
          FROM public.protocol_execution_intent AS intent
          JOIN public.protocol_project_location AS mapping
            ON mapping.id = intent.mapping_id
    """,
}

APPROVAL_ACTIONS = ("approve",)


def build_source_rows_sql() -> str:
    direct = [
        f"""SELECT '{collection}'::text AS source_collection,
                      source_row.id AS source_id,
                      source_row.location_id AS location_id
                 FROM public.{collection} AS source_row"""
        for collection in DIRECT_LOCATION_SOURCES
    ]
    return "\nUNION ALL\n".join([*direct, *CUSTOM_SOURCE_SQL.values()])


def build_workflow_history_query() -> str:
    known = ", ".join(f"'{name}'" for name in (*DIRECT_LOCATION_SOURCES, *CUSTOM_SOURCE_SQL))
    return f"""
        WITH source_rows AS ({build_source_rows_sql()}),
        classified AS (
            SELECT
                CASE WHEN history.collection IS NOT NULL
                           AND history.collection IN ({known})
                     THEN history.collection ELSE 'unsupported' END AS collection,
                CASE
                    WHEN history.collection IS NULL
                         OR history.collection NOT IN ({known}) THEN 'unsupported'
                    WHEN source.source_id IS NULL OR source.location_id IS NULL
                         OR location.id IS NULL THEN 'unresolved'
                    ELSE 'resolved'
                END AS lineage_class
              FROM public.workflow_history AS history
              LEFT JOIN source_rows AS source
                ON source.source_collection = history.collection
               AND source.source_id = history.record_id
              LEFT JOIN public.location AS location
                ON location.id = source.location_id
        )
        SELECT collection, lineage_class, COUNT(*)::bigint AS row_count
          FROM classified
         GROUP BY collection, lineage_class
         ORDER BY collection, lineage_class
    """


def build_approval_query() -> str:
    known = ", ".join(f"'{name}'" for name in (*DIRECT_LOCATION_SOURCES, *CUSTOM_SOURCE_SQL))
    action_values = ", ".join(f"'{name}'" for name in APPROVAL_ACTIONS)
    return f"""
        WITH source_rows AS ({build_source_rows_sql()}),
        classified AS (
            SELECT
                CASE WHEN approval.collection IS NOT NULL
                           AND approval.collection IN ({known})
                     THEN approval.collection ELSE 'unsupported' END AS collection,
                CASE WHEN approval.action IS NOT NULL
                          AND approval.action IN ({action_values})
                     THEN approval.action ELSE 'other' END AS action,
                CASE
                    WHEN approval.collection IS NULL
                         OR approval.collection NOT IN ({known}) THEN 'unsupported'
                    WHEN source.source_id IS NULL OR source.location_id IS NULL
                         OR location.id IS NULL THEN 'unresolved'
                    ELSE 'resolved'
                END AS lineage_class
              FROM public.approval AS approval
              LEFT JOIN source_rows AS source
                ON source.source_collection = approval.collection
               AND source.source_id = approval.record_id
              LEFT JOIN public.location AS location
                ON location.id = source.location_id
        )
        SELECT collection, action, lineage_class, COUNT(*)::bigint AS row_count
          FROM classified
         GROUP BY collection, action, lineage_class
         ORDER BY collection, action, lineage_class
    """


def _count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("aggregate query returned an invalid count")
    return value


def _safe_collection(value: Any) -> str:
    allowed = set(DIRECT_LOCATION_SOURCES) | set(CUSTOM_SOURCE_SQL)
    return value if isinstance(value, str) and value in allowed else "unsupported"


def _safe_lineage_class(value: Any) -> str:
    allowed = ("resolved", "unresolved", "unsupported")
    return value if isinstance(value, str) and value in allowed else "unsupported"


def get_aggregate_counts(connection: Any) -> dict[str, Any]:
    """Run both count-only queries on an already-open connection."""
    report: dict[str, Any] = {
        "workflow_history": {"counts": [], "totals": {"resolved": 0, "unresolved": 0, "unsupported": 0}},
        "approval": {"counts": [], "totals": {"resolved": 0, "unresolved": 0, "unsupported": 0}},
    }
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")

        cursor.execute(build_workflow_history_query())
        for raw_collection, raw_class, raw_count in cursor.fetchall():
            collection = _safe_collection(raw_collection)
            lineage_class = _safe_lineage_class(raw_class)
            count = _count(raw_count)
            report["workflow_history"]["counts"].append({
                "collection": collection,
                "lineage": lineage_class,
                "count": count,
            })
            report["workflow_history"]["totals"][lineage_class] += count

        cursor.execute(build_approval_query())
        for raw_collection, raw_action, raw_class, raw_count in cursor.fetchall():
            collection = _safe_collection(raw_collection)
            action = raw_action if isinstance(raw_action, str) and raw_action in APPROVAL_ACTIONS else "other"
            lineage_class = _safe_lineage_class(raw_class)
            count = _count(raw_count)
            report["approval"]["counts"].append({
                "collection": collection,
                "action": action,
                "lineage": lineage_class,
                "count": count,
            })
            report["approval"]["totals"][lineage_class] += count
    return report


def main() -> int:
    dsn = os.environ.get("DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN", "")
    if not dsn:
        print(json.dumps({
            "result": "blocked",
            "reason": "DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN must select the read-only target",
        }, sort_keys=True))
        return 2

    connection = None
    try:
        connection = psycopg2.connect(
            dsn,
            connect_timeout=8,
            application_name="kokonut-directus-polymorphic-lineage-preflight",
        )
        connection.autocommit = False
        report = get_aggregate_counts(connection)
        # End the repeatable-read snapshot without retaining any transaction
        # state. Read-only mode prevents writes even if a future edit errs.
        connection.rollback()
    except Exception as exc:  # noqa: BLE001 - never emit DSN or DB row details.
        if connection is not None:
            connection.rollback()
        print(json.dumps({
            "result": "failed",
            "error_type": type(exc).__name__,
            "sqlstate": getattr(exc, "pgcode", None),
        }, sort_keys=True))
        return 1
    finally:
        if connection is not None:
            connection.close()

    print(json.dumps({"result": "completed", **report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
