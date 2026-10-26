"""Tenant-scoped, read-only nutrient balance summaries."""

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


def get_location_nutrient_balances(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return grouped N/P/K balances from the verified/published balance view."""
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
                  FROM (
                      SELECT season, crop_name
                        FROM v_nutrient_balance
                       WHERE location_id = %s::uuid
                       GROUP BY season, crop_name
                  ) AS grouped_balances
                """,
                (location_id,),
            )
            total_summaries = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT season, crop_name, COUNT(*) AS budget_count,
                       SUM(area_ha) AS area_ha,
                       SUM(nitrogen_input_kg) AS nitrogen_input_kg,
                       SUM(nitrogen_removal_kg) AS nitrogen_removal_kg,
                       SUM(nitrogen_surplus_kg) AS nitrogen_surplus_kg,
                       SUM(phosphorus_input_kg) AS phosphorus_input_kg,
                       SUM(phosphorus_removal_kg) AS phosphorus_removal_kg,
                       SUM(phosphorus_surplus_kg) AS phosphorus_surplus_kg,
                       SUM(potassium_input_kg) AS potassium_input_kg,
                       SUM(potassium_removal_kg) AS potassium_removal_kg,
                       SUM(potassium_surplus_kg) AS potassium_surplus_kg
                  FROM v_nutrient_balance
                 WHERE location_id = %s::uuid
                 GROUP BY season, crop_name
                 ORDER BY season DESC, crop_name ASC NULLS LAST
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        balances = []
        for row in rows[:limit]:
            balances.append(
                {
                    "season": row["season"],
                    "crop_name": row["crop_name"],
                    "budget_count": int(row["budget_count"] or 0),
                    "area_ha": _number(row["area_ha"]),
                    "nitrogen": {
                        "input_kg": _number(row["nitrogen_input_kg"]),
                        "removal_kg": _number(row["nitrogen_removal_kg"]),
                        "surplus_kg": _number(row["nitrogen_surplus_kg"]),
                    },
                    "phosphorus": {
                        "input_kg": _number(row["phosphorus_input_kg"]),
                        "removal_kg": _number(row["phosphorus_removal_kg"]),
                        "surplus_kg": _number(row["phosphorus_surplus_kg"]),
                    },
                    "potassium": {
                        "input_kg": _number(row["potassium_input_kg"]),
                        "removal_kg": _number(row["potassium_removal_kg"]),
                        "surplus_kg": _number(row["potassium_surplus_kg"]),
                    },
                }
            )

        return {
            "location_id": location_id,
            "total_summaries": total_summaries,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
            "balances": balances,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
