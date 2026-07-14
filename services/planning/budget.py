"""Financial planning / budgeting service (FP&A)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Mapping, Optional, Sequence

from psycopg2.extras import RealDictCursor

from services.common.logging import get_logger
from services.ingestion.base import get_db
from services.planning import model
from services.workflow_specs.budget import BUDGET

logger = get_logger("planning.budget")


def create_plan(
    conn,
    organization_id: str,
    name: str,
    period_start: str,
    period_end: str,
    currency: str = "USD",
    objective_id: Optional[str] = None,
    created_by_type: str = "system",
    created_by_id: Optional[str] = None,
) -> Mapping:
    """Create a financial plan in ``draft``."""
    conn2, own = model._conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO financial_plan (
                    organization_id, objective_id, name, period_start, period_end,
                    currency, status, created_by_type, created_by_id
                ) VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s, %s)
                RETURNING *
                """,
                (
                    uuid.UUID(organization_id), uuid.UUID(objective_id) if objective_id else None,
                    name, _as_date(period_start), _as_date(period_end), currency,
                    created_by_type, uuid.UUID(created_by_id) if created_by_id else None,
                ),
            )
            row = cur.fetchone()
            conn2.commit()
            return row
    finally:
        if own:
            conn2.close()


def add_budget_line(
    conn,
    plan_id: str,
    category: str,
    amount: float,
    location_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Mapping:
    conn2, own = model._conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO budget_line (plan_id, category, location_id, amount, notes)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (uuid.UUID(plan_id), category, uuid.UUID(location_id) if location_id else None, amount, notes),
            )
            row = cur.fetchone()
            conn2.commit()
            return row
    finally:
        if own:
            conn2.close()


def get_plan(conn, plan_id: str) -> Optional[Mapping]:
    return model._row(conn, "SELECT * FROM financial_plan WHERE id = %s", (uuid.UUID(plan_id),))


def list_plans(conn, organization_id: str, status: Optional[str] = None) -> Sequence[Mapping]:
    clauses = ["organization_id = %s"]
    params: list = [uuid.UUID(organization_id)]
    if status:
        clauses.append("status = %s")
        params.append(status)
    return model._rows(
        conn,
        f"SELECT * FROM financial_plan WHERE {' AND '.join(clauses)} ORDER BY created_at DESC",
        tuple(params),
    )


def approve(conn, plan_id: str, actor_type: str, actor_id: Optional[str] = None, note: Optional[str] = None) -> Mapping:
    return model.governed_transition(conn, "financial_plan", plan_id, "approved", BUDGET, actor_type, actor_id, "approve", note)


def activate(conn, plan_id: str, actor_type: str, actor_id: Optional[str] = None, note: Optional[str] = None) -> Mapping:
    return model.governed_transition(conn, "financial_plan", plan_id, "active", BUDGET, actor_type, actor_id, "activate", note)


def close(conn, plan_id: str, actor_type: str, actor_id: Optional[str] = None, note: Optional[str] = None) -> Mapping:
    return model.governed_transition(conn, "financial_plan", plan_id, "closed", BUDGET, actor_type, actor_id, "close", note)


def cancel(conn, plan_id: str, actor_type: str, actor_id: Optional[str] = None, note: Optional[str] = None) -> Mapping:
    return model.governed_transition(conn, "financial_plan", plan_id, "cancelled", BUDGET, actor_type, actor_id, "cancel", note)


def actuals_rollup(conn, plan_id: str) -> Sequence[Mapping]:
    """Roll planned budget lines up against verified actual expense/revenue events.

    Actuals are derived (not stored) from ``expense_event`` / ``revenue_event`` by
    category and period, filtered to the budget line's location when set.
    """
    plan = get_plan(conn, plan_id)
    if not plan:
        raise ValueError(f"plan not found: {plan_id}")
    lines = model._rows(conn, "SELECT * FROM budget_line WHERE plan_id = %s", (uuid.UUID(plan_id),))
    start, end = plan["period_start"], plan["period_end"]
    out = []
    for line in lines:
        loc = line["location_id"]
        expense = _sum_events(
            conn, "expense_event", loc, line["category"], start, end,
        )
        revenue = _sum_events(
            conn, "revenue_event", loc, line["category"], start, end,
        )
        out.append({
            "budget_line_id": str(line["id"]),
            "category": line["category"],
            "location_id": str(loc) if loc else None,
            "planned": float(line["amount"]),
            "actual_expense": expense,
            "actual_revenue": revenue,
            "variance": float(line["amount"]) - expense,
        })
    return out


def _sum_events(conn, table: str, location_id, category: str, start: date, end: date) -> float:
    clauses = ["category = %s", "status = 'verified'",
               "expense_date BETWEEN %s AND %s" if table == "expense_event" else "revenue_date BETWEEN %s AND %s"]
    params: list = [category, start, end]
    if location_id:
        clauses.append("location_id = %s")
        params.append(location_id)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM {table} WHERE {' AND '.join(clauses)}",
            tuple(params),
        )
        return float(cur.fetchone()[0] or 0)


def _as_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
