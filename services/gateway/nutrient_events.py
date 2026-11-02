"""Tenant-scoped, read-only nutrient input and removal event reads."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MAX_OFFSET = 10_000
_EVENT_TYPES = {"inputs", "removals"}


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


def get_location_nutrient_events(
    operator_id: str,
    location_id: str,
    event_type: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded recorded/verified inputs or harvest removals.

    Child records are joined through their parent budget's location. Parent
    lifecycle is returned separately and is not silently promoted. Plot IDs are
    exposed only when the referenced plot belongs to the authorized location.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    if event_type not in _EVENT_TYPES:
        raise ValueError("event_type must be 'inputs' or 'removals'")
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
            if event_type == "inputs":
                cur.execute(
                    """
                    SELECT COUNT(*)
                      FROM nutrient_input AS event
                      JOIN nutrient_budget AS budget ON budget.id = event.budget_id
                     WHERE budget.location_id = %s::uuid
                       AND event.status IN ('recorded', 'verified')
                    """,
                    (location_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*)
                      FROM nutrient_removal AS event
                      JOIN nutrient_budget AS budget ON budget.id = event.budget_id
                     WHERE budget.location_id = %s::uuid
                       AND event.status IN ('recorded', 'verified')
                    """,
                    (location_id,),
                )
            total_events = int(cur.fetchone()[0] or 0)

            if event_type == "inputs":
                cur.execute(
                    """
                    SELECT event.id, CASE WHEN farm.id IS NOT NULL THEN plot.id END AS plot_id,
                           budget.season, budget.crop_name AS budget_crop_name,
                           budget.status AS budget_status, event.status AS event_status,
                           event.input_date, event.input_type, event.product_name,
                           event.nitrogen_kg, event.phosphorus_kg, event.potassium_kg,
                           event.application_rate, event.rate_unit,
                           event.cost, event.cost_currency_code
                      FROM nutrient_input AS event
                      JOIN nutrient_budget AS budget ON budget.id = event.budget_id
                      LEFT JOIN plot AS plot ON plot.id = budget.plot_id
                      LEFT JOIN farm AS farm
                        ON farm.id = plot.farm_id
                       AND farm.location_id = budget.location_id
                     WHERE budget.location_id = %s::uuid
                       AND event.status IN ('recorded', 'verified')
                     ORDER BY event.input_date DESC, event.id DESC
                     LIMIT %s OFFSET %s
                    """,
                    (location_id, limit + 1, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT event.id, CASE WHEN farm.id IS NOT NULL THEN plot.id END AS plot_id,
                           budget.season, budget.crop_name AS budget_crop_name,
                           budget.status AS budget_status, event.status AS event_status,
                           event.harvest_date, event.crop_name, event.yield_amount,
                           event.yield_unit, event.nitrogen_kg, event.phosphorus_kg,
                           event.potassium_kg
                      FROM nutrient_removal AS event
                      JOIN nutrient_budget AS budget ON budget.id = event.budget_id
                      LEFT JOIN plot AS plot ON plot.id = budget.plot_id
                      LEFT JOIN farm AS farm
                        ON farm.id = plot.farm_id
                       AND farm.location_id = budget.location_id
                     WHERE budget.location_id = %s::uuid
                       AND event.status IN ('recorded', 'verified')
                     ORDER BY event.harvest_date DESC, event.id DESC
                     LIMIT %s OFFSET %s
                    """,
                    (location_id, limit + 1, offset),
                )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        events = []
        for row in rows[:limit]:
            item = {
                "event_id": str(row["id"]),
                "plot_id": str(row["plot_id"]) if row["plot_id"] else None,
                "season": row["season"],
                "budget_crop_name": row["budget_crop_name"],
                "budget_status": row["budget_status"],
                "event_status": row["event_status"],
                "nutrients_kg": {
                    "nitrogen": _number(row["nitrogen_kg"]),
                    "phosphorus": _number(row["phosphorus_kg"]),
                    "potassium": _number(row["potassium_kg"]),
                },
            }
            if event_type == "inputs":
                if row["cost"] is None:
                    cost_status = "not_recorded"
                    cost = None
                elif row["cost_currency_code"] is None:
                    cost_status = "currency_unclassified"
                    cost = None
                else:
                    cost_status = "classified"
                    cost = {
                        "amount": _number(row["cost"]),
                        "currency_code": row["cost_currency_code"],
                    }
                item.update(
                    {
                        "input_date": _date(row["input_date"]),
                        "input_type": row["input_type"],
                        "product_name": row["product_name"],
                        "application_rate": _number(row["application_rate"]),
                        "rate_unit": row["rate_unit"],
                        "cost": cost,
                        "cost_status": cost_status,
                    }
                )
            else:
                item.update(
                    {
                        "harvest_date": _date(row["harvest_date"]),
                        "crop_name": row["crop_name"],
                        "yield_amount": _number(row["yield_amount"]),
                        "yield_unit": row["yield_unit"],
                    }
                )
            events.append(item)

        return {
            "location_id": location_id,
            "event_type": event_type,
            "total_events": total_events,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit and offset + limit <= _MAX_OFFSET,
            "events": events,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
