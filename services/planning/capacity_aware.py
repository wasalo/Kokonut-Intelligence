"""Capacity-aware planning projections."""

from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return dict(row)


def work_queue(conn, *, organization_id: Optional[str] = None, scope_type: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params = []
    if organization_id:
        clauses.append("organization_id = %s::uuid")
        params.append(organization_id)
    if scope_type:
        clauses.append("inferred_scope_type = %s")
        params.append(scope_type)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_capacity_aware_work_queue{where} ORDER BY demand_priority_rank DESC NULLS LAST, priority DESC, due_at NULLS LAST", params)
        return [_clean(row) for row in cur.fetchall()]


def portfolio_health(conn, *, scope_type: Optional[str] = None, scope_id: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params = []
    if scope_type:
        clauses.append("scope_type = %s")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = %s::uuid")
        params.append(scope_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_operating_portfolio_health{where} ORDER BY scope_type, scope_id", params)
        return [_clean(row) for row in cur.fetchall()]
