"""Competitive-position reporting for strategy and business-plan surfaces."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def health(conn, strategy_plan_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_strategy_competitive_health WHERE strategy_plan_id = %s::uuid", (strategy_plan_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("strategy competitive health not found")
        return _clean(row)


def report(conn, strategy_plan_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM competitive_landscape WHERE strategy_plan_id = %s::uuid ORDER BY period_end DESC", (strategy_plan_id,))
        landscapes = [_clean(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM strategy_position WHERE strategy_plan_id = %s::uuid ORDER BY target_name", (strategy_plan_id,))
        positions = [_clean(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_strategy_advantage_fit WHERE strategy_plan_id = %s::uuid ORDER BY defensibility_score DESC NULLS LAST", (strategy_plan_id,))
        advantages = [_clean(row) for row in cur.fetchall()]
        return {"strategy_plan_id": strategy_plan_id, "health": health(conn, strategy_plan_id), "landscapes": landscapes, "positions": positions, "advantages": advantages}
