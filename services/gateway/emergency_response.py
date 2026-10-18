"""Tenant-scoped aggregate reads for emergency response operations."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def get_emergency_response_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return aggregate incident/response data for one authorized location.

    Free-text descriptions, response actions, support details, lessons, and
    per-incident records remain private and are not included in this summary.
    """
    try:
        operator_id = str(UUID(operator_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="emergency_response",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total_incidents,
                       COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_incidents,
                       COUNT(*) FILTER (WHERE status = 'escalated') AS escalated_incidents,
                       COUNT(*) FILTER (WHERE recovery_date IS NOT NULL) AS recovered_incidents,
                       AVG(recovery_date - detection_date)
                           FILTER (WHERE recovery_date IS NOT NULL) AS avg_response_time_days,
                       COUNT(*) FILTER (
                           WHERE response_deadline IS NOT NULL AND recovery_date IS NOT NULL
                       ) AS deadline_assessed_incidents,
                       COUNT(*) FILTER (
                           WHERE response_deadline IS NOT NULL
                             AND recovery_date IS NOT NULL
                             AND recovery_date <= response_deadline
                       ) AS deadline_met_incidents,
                       COALESCE(SUM(financial_impact_usd), 0) AS financial_impact_usd,
                       COALESCE(AVG(affected_area_pct), 0) AS avg_affected_area_pct
                  FROM emergency_incident
                 WHERE location_id = %s::uuid
                """,
                (location_id,),
            )
            totals = cur.fetchone()
            cur.execute(
                """
                SELECT incident_type, COUNT(*) AS count,
                       COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_count,
                       COUNT(*) FILTER (WHERE status = 'escalated') AS escalated_count,
                       COALESCE(AVG(affected_area_pct), 0) AS avg_affected_area_pct,
                       COALESCE(SUM(financial_impact_usd), 0) AS financial_impact_usd
                  FROM emergency_incident
                 WHERE location_id = %s::uuid
                 GROUP BY incident_type
                 ORDER BY count DESC, incident_type
                """,
                (location_id,),
            )
            by_type_rows = cur.fetchall()
            cur.execute(
                """
                SELECT severity, COUNT(*) AS count,
                       COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_count,
                       COUNT(*) FILTER (WHERE status = 'escalated') AS escalated_count,
                       COALESCE(AVG(affected_area_pct), 0) AS avg_affected_area_pct,
                       COALESCE(SUM(financial_impact_usd), 0) AS financial_impact_usd
                  FROM emergency_incident
                 WHERE location_id = %s::uuid
                 GROUP BY severity
                 ORDER BY count DESC, severity
                """,
                (location_id,),
            )
            by_severity_rows = cur.fetchall()

        deadline_assessed = totals[5] or 0
        deadline_met = totals[6] or 0
        return {
            "location_id": location_id,
            "total_incidents": totals[0] or 0,
            "resolved_incidents": totals[1] or 0,
            "escalated_incidents": totals[2] or 0,
            "recovered_incidents": totals[3] or 0,
            "avg_response_time_days": (
                round(float(totals[4]), 1) if totals[4] is not None else None
            ),
            "deadline_assessed_incidents": deadline_assessed,
            "deadline_met_incidents": deadline_met,
            "deadline_compliance_pct": (
                round(deadline_met / deadline_assessed * 100, 1)
                if deadline_assessed
                else None
            ),
            "financial_impact_usd": round(float(totals[7] or 0), 2),
            "avg_affected_area_pct": round(float(totals[8] or 0), 1),
            "by_type": [_group_row(row, "incident_type") for row in by_type_rows],
            "by_severity": [_group_row(row, "severity") for row in by_severity_rows],
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def _group_row(row, group_name: str) -> dict:
    return {
        group_name: row[0],
        "count": row[1] or 0,
        "resolved_count": row[2] or 0,
        "escalated_count": row[3] or 0,
        "avg_affected_area_pct": round(float(row[4] or 0), 1),
        "financial_impact_usd": round(float(row[5] or 0), 2),
    }
