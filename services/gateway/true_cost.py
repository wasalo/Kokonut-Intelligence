"""Tenant-scoped, read-only true-cost accounting Gateway queries."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.analytics.systems_thinking import (
    compute_capital_flow_summary,
    compute_cross_capital_dependencies,
)
from services.analytics.true_cost_accounting import (
    compute_hidden_cost_summary,
    compute_natural_capital_valuation,
    compute_social_impact_valuation,
    compute_true_cost_statement,
)
from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def get_true_cost_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Compute bounded true-cost aggregates for one authorized farm location.

    The transaction is read-only and installs database-verified operator
    tenant context before any domain query. No row-level observations or
    private evidence are returned by this endpoint.
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
            resource="true_cost_accounting",
            action="read",
        )

        return {
            "location_id": location_id,
            "true_cost_statement": compute_true_cost_statement(conn, location_id),
            "hidden_costs": compute_hidden_cost_summary(conn, location_id),
            "natural_capital": compute_natural_capital_valuation(conn, location_id),
            "social_impact": compute_social_impact_valuation(conn, location_id),
            "capital_flows": compute_capital_flow_summary(conn, location_id),
            "cross_capital_dependencies": compute_cross_capital_dependencies(
                conn, location_id
            ),
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
