"""Location-scoped, read-only report review queries for the optional console."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID


class ReportPayloadTooLarge(ValueError):
    """Raised when a report exceeds the browser review response bound."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def list_submitted_reports(
    operator_id: str,
    location_id: str,
    limit: int = 50,
    *,
    connection_factory: Callable | None = None,
) -> list[dict]:
    """Return a bounded summary list; report payloads are fetched separately."""
    try:
        operator_id = str(UUID(operator_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")
            cur.execute(
                """SELECT rs.id, rs.report_name, rs.report_type, rs.status,
                          rs.period_start, rs.period_end, rs.snapshot_hash,
                          rs.created_at, l.name AS location_name
                     FROM report_snapshot AS rs
                     JOIN location AS l ON l.id = rs.location_id
                    WHERE rs.location_id = %s::uuid
                      AND rs.status = 'submitted'
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'report_snapshot_review'
                             AND grant_row.action = 'read'
                             AND grant_row.location_id = rs.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                    ORDER BY rs.created_at DESC, rs.id DESC
                    LIMIT %s""",
                (location_id, operator_id, limit),
            )
            columns = [description.name for description in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        return [
            {
                **row,
                "id": str(row["id"]),
                "period_start": row["period_start"].isoformat() if row["period_start"] else None,
                "period_end": row["period_end"].isoformat() if row["period_end"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_submitted_report(
    operator_id: str,
    report_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Return one submitted report only when it belongs to the granted location."""
    try:
        operator_id = str(UUID(operator_id))
        report_id = str(UUID(report_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator, report, or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")
            cur.execute(
                """SELECT rs.id, rs.report_name, rs.report_type, rs.status,
                          rs.period_start, rs.period_end, rs.snapshot_hash,
                          rs.created_at,
                          CASE WHEN octet_length(rs.report_data::text) <= 524288
                               THEN rs.report_data ELSE NULL END AS report_data,
                          octet_length(rs.report_data::text) AS report_size,
                          l.name AS location_name
                     FROM report_snapshot AS rs
                     JOIN location AS l ON l.id = rs.location_id
                    WHERE rs.id = %s::uuid
                      AND rs.location_id = %s::uuid
                      AND rs.status = 'submitted'
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'report_snapshot_review'
                             AND grant_row.action = 'read'
                             AND grant_row.location_id = rs.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                    LIMIT 1""",
                (report_id, location_id, operator_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [description.name for description in cur.description]
            result = dict(zip(columns, row))
        if result["report_data"] is None and result["report_size"] > 524288:
            raise ReportPayloadTooLarge("Report exceeds the 512 KiB console read limit")
        result.pop("report_size", None)
        result["id"] = str(result["id"])
        result["period_start"] = result["period_start"].isoformat() if result["period_start"] else None
        result["period_end"] = result["period_end"].isoformat() if result["period_end"] else None
        result["created_at"] = result["created_at"].isoformat() if result["created_at"] else None
        return result
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
