"""Integrated strategy execution rollups and review snapshots."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def dashboard(conn, *, strategy_plan_id: Optional[str] = None, scope_type: Optional[str] = None, scope_id: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params = []
    if strategy_plan_id:
        clauses.append("strategy_plan_id = %s::uuid")
        params.append(strategy_plan_id)
    if scope_type:
        clauses.append("scope_type = %s")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = %s::uuid")
        params.append(scope_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_strategy_kernel_execution{where} ORDER BY scope_type, scope_id, version DESC", params)
        return [_clean(row) for row in cur.fetchall()]


def capture_snapshot(conn, strategy_plan_id: str, *, captured_by_party_id: Optional[str] = None, review_note: Optional[str] = None) -> Dict[str, Any]:
    rows = dashboard(conn, strategy_plan_id=strategy_plan_id)
    if not rows:
        raise ValueError("strategy plan execution state not found")
    summary = rows[0]
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_review_snapshot
            (strategy_plan_id, captured_by_party_id, summary, review_note)
            VALUES (%s::uuid, %s::uuid, %s::jsonb, %s) RETURNING *""", (strategy_plan_id, captured_by_party_id, json.dumps(summary, default=str), review_note))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def list_snapshots(conn, strategy_plan_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM strategy_review_snapshot WHERE strategy_plan_id = %s::uuid ORDER BY captured_at DESC", (strategy_plan_id,))
        return [_clean(row) for row in cur.fetchall()]
