"""Tenant-scoped read-only aggregates for verified farm energy readings."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _iso(value):
    return value.isoformat() if value is not None else None


def get_location_energy_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded kWh aggregates for verified/approved readings only.

    Costs, notes, source names, device identifiers, and arbitrary metadata are
    deliberately excluded. The grouping dimensions are constrained by the
    source schema's CHECK values, so result size is bounded independently of
    farm history volume.
    """
    try:
        operator_id = str(UUID(str(operator_id)))
        location_id = str(UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="energy_monitoring",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT er.reading_type,
                       es.source_type,
                       COALESCE(er.activity_type, 'unspecified') AS activity_type,
                       COUNT(*)::bigint AS reading_count,
                       SUM(er.kwh)::numeric AS total_kwh,
                       MIN(er.reading_date) AS first_reading_date,
                       MAX(er.reading_date) AS last_reading_date
                  FROM energy_reading AS er
                  JOIN energy_source AS es
                    ON es.id = er.source_id
                   AND es.location_id = er.location_id
                 WHERE er.location_id = %s::uuid
                   AND er.status IN ('verified', 'approved')
                 GROUP BY er.reading_type, es.source_type,
                          COALESCE(er.activity_type, 'unspecified')
                 ORDER BY er.reading_type, es.source_type,
                          COALESCE(er.activity_type, 'unspecified')
                """,
                (location_id,),
            )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        groups = [
            {
                "reading_type": row["reading_type"],
                "source_type": row["source_type"],
                "activity_type": row["activity_type"],
                "reading_count": int(row["reading_count"] or 0),
                "total_kwh": float(row["total_kwh"] or 0),
                "first_reading_date": _iso(row["first_reading_date"]),
                "last_reading_date": _iso(row["last_reading_date"]),
            }
            for row in rows
        ]
        return {
            "location_id": location_id,
            "unit": "kWh",
            "verified_reading_count": sum(row["reading_count"] for row in groups),
            "groups": groups,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
