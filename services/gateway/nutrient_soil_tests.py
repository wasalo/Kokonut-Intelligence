"""Tenant-scoped, read-only soil-test observations and recommendations."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MAX_OFFSET = 10_000


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {label} identifier") from exc


def _page(limit: int, offset: int) -> tuple[int, int]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {_MAX_PAGE_SIZE}")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= _MAX_OFFSET:
        raise ValueError(f"offset must be between 0 and {_MAX_OFFSET}")
    return limit, offset


def _number(value):
    return float(value) if value is not None else None


def _date(value):
    return value.isoformat() if value is not None else None


def get_location_soil_tests(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded recorded/verified soil tests for one authorized location.

    Plot identifiers are returned only when the referenced plot belongs to the
    requested location. Notes and arbitrary metadata are never selected.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    limit, offset = _page(limit, offset)

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
            resource="nutrient_budget",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM soil_test_recommendation AS soil
                 WHERE soil.location_id = %s::uuid
                   AND soil.status IN ('recorded', 'verified')
                """,
                (location_id,),
            )
            total_tests = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT soil.id,
                       CASE WHEN farm.id IS NOT NULL THEN plot.id END AS plot_id,
                       soil.test_date,
                       soil.soil_ph, soil.organic_matter_pct,
                       soil.nitrogen_ppm, soil.phosphorus_ppm,
                       soil.potassium_ppm, soil.cec,
                       soil.recommended_n_kg_ha, soil.recommended_p_kg_ha,
                       soil.recommended_k_kg_ha, soil.status
                  FROM soil_test_recommendation AS soil
                  LEFT JOIN plot AS plot ON plot.id = soil.plot_id
                  LEFT JOIN farm AS farm
                    ON farm.id = plot.farm_id
                   AND farm.location_id = soil.location_id
                 WHERE soil.location_id = %s::uuid
                   AND soil.status IN ('recorded', 'verified')
                 ORDER BY soil.test_date DESC, soil.id DESC
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        tests = []
        for row in rows[:limit]:
            tests.append(
                {
                    "test_id": str(row["id"]),
                    "plot_id": str(row["plot_id"]) if row["plot_id"] else None,
                    "test_date": _date(row["test_date"]),
                    "status": row["status"],
                    "measurements": {
                        "soil_ph": _number(row["soil_ph"]),
                        "organic_matter_pct": _number(row["organic_matter_pct"]),
                        "nitrogen_ppm": _number(row["nitrogen_ppm"]),
                        "phosphorus_ppm": _number(row["phosphorus_ppm"]),
                        "potassium_ppm": _number(row["potassium_ppm"]),
                        "cec": _number(row["cec"]),
                    },
                    "recommendations_kg_ha": {
                        "nitrogen": _number(row["recommended_n_kg_ha"]),
                        "phosphorus": _number(row["recommended_p_kg_ha"]),
                        "potassium": _number(row["recommended_k_kg_ha"]),
                    },
                }
            )

        return {
            "location_id": location_id,
            "total_tests": total_tests,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
            "soil_tests": tests,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
