"""Tenant-scoped, read-only harvest-yield projections for the Gateway."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _number(value):
    return float(value) if value is not None else None


def _date(value):
    return value.isoformat() if value is not None else None


def _rows(cur) -> list[dict]:
    columns = [column[0] for column in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_location_yield_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return verified yield aggregates and a bounded recent-harvest list.

    Draft and submitted observations are intentionally excluded. The response
    omits source identifiers, actor fields, metadata, and private evidence.
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
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="yield_monitoring",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total_observations,
                       MIN(harvest_date) AS first_harvest,
                       MAX(harvest_date) AS last_harvest
                  FROM harvest_yield_observation
                 WHERE location_id = %s::uuid
                   AND status IN ('verified', 'published')
                """,
                (location_id,),
            )
            overall = cur.fetchone()

            cur.execute(
                """
                SELECT yield_unit,
                       COUNT(*) AS observations,
                       AVG(yield_amount) AS avg_yield,
                       SUM(total_yield) AS total_yield
                  FROM harvest_yield_observation
                 WHERE location_id = %s::uuid
                   AND status IN ('verified', 'published')
                 GROUP BY yield_unit
                 ORDER BY yield_unit
                """,
                (location_id,),
            )
            totals_by_unit = _rows(cur)

            cur.execute(
                """
                SELECT crop_name, yield_unit,
                       COUNT(*) AS observations,
                       AVG(yield_amount) AS avg_yield,
                       MIN(yield_amount) AS min_yield,
                       MAX(yield_amount) AS max_yield,
                       STDDEV(yield_amount) AS stddev_yield,
                       SUM(total_yield) AS total_production
                  FROM harvest_yield_observation
                 WHERE location_id = %s::uuid
                   AND status IN ('verified', 'published')
                 GROUP BY crop_name, yield_unit
                 ORDER BY total_production DESC NULLS LAST, crop_name, yield_unit
                """,
                (location_id,),
            )
            crops = _rows(cur)

            cur.execute(
                """
                SELECT harvest_date, crop_name, yield_amount, yield_unit, area_ha,
                       total_yield, grade
                  FROM harvest_yield_observation
                 WHERE location_id = %s::uuid
                   AND status IN ('verified', 'published')
                 ORDER BY harvest_date DESC, id
                 LIMIT 10
                """,
                (location_id,),
            )
            recent = _rows(cur)

        return {
            "location_id": location_id,
            "total_observations": int(overall[0] or 0),
            "first_harvest": _date(overall[1]),
            "last_harvest": _date(overall[2]),
            "totals_by_yield_unit": [
                {
                    **row,
                    "observations": int(row["observations"] or 0),
                    "avg_yield": _number(row["avg_yield"]),
                    "total_yield": _number(row["total_yield"]),
                }
                for row in totals_by_unit
            ],
            "crops": [
                {
                    **row,
                    "observations": int(row["observations"] or 0),
                    "avg_yield": _number(row["avg_yield"]),
                    "min_yield": _number(row["min_yield"]),
                    "max_yield": _number(row["max_yield"]),
                    "stddev_yield": _number(row["stddev_yield"]),
                    "total_production": _number(row["total_production"]),
                }
                for row in crops
            ],
            "recent_harvests": [
                {
                    **row,
                    "harvest_date": _date(row["harvest_date"]),
                    "yield_amount": _number(row["yield_amount"]),
                    "yield_unit": row["yield_unit"],
                    "area_ha": _number(row["area_ha"]),
                    "total_yield": _number(row["total_yield"]),
                }
                for row in recent
            ],
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
