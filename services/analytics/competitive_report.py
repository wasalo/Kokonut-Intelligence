"""Competitive-position reporting for strategy and business-plan surfaces."""

from __future__ import annotations

import uuid
from typing import Any, Dict

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def health(conn, strategy_plan_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT strategy_plan_id, scope_type, scope_id, landscape_count,
                      verified_landscape_count, average_force_pressure_score,
                      unreviewed_material_signal_count, approved_position_count,
                      verified_advantage_count, unlinked_advantage_count,
                      partial_advantage_count, open_competitive_review_count
               FROM v_strategy_competitive_health
               WHERE strategy_plan_id = %s::uuid""",
            (strategy_plan_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("strategy competitive health not found")
        return _clean(row)


def report(conn, strategy_plan_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT id, strategy_plan_id, scope_type, scope_id, industry,
                      geography, period_start, period_end, status, confidence,
                      summary, created_by_party_id, verified_by_party_id,
                      verified_at, created_at, updated_at
               FROM competitive_landscape
               WHERE strategy_plan_id = %s::uuid
               ORDER BY period_end DESC""",
            (strategy_plan_id,),
        )
        landscapes = [_clean(row) for row in cur.fetchall()]
        cur.execute(
            """SELECT id, strategy_plan_id, landscape_id, target_type, target_id,
                      target_name, customer_needs, value_drivers, value_proposition,
                      differentiation, alternatives, excluded_scope,
                      geographic_scope, product_service_scope, position_score,
                      confidence, status, visibility, created_by_party_id,
                      approved_by_party_id, approved_at, created_at, updated_at
               FROM strategy_position
               WHERE strategy_plan_id = %s::uuid
               ORDER BY target_name""",
            (strategy_plan_id,),
        )
        positions = [_clean(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT advantage_id, strategy_plan_id, name, defensibility_score, status, "
            "link_count, capability_link_count, choice_link_count, investment_link_count, fit_status "
            "FROM v_strategy_advantage_fit WHERE strategy_plan_id = %s::uuid "
            "ORDER BY defensibility_score DESC NULLS LAST",
            (strategy_plan_id,),
        )
        advantages = [_clean(row) for row in cur.fetchall()]
        return {"strategy_plan_id": strategy_plan_id, "health": health(conn, strategy_plan_id), "landscapes": landscapes, "positions": positions, "advantages": advantages}
