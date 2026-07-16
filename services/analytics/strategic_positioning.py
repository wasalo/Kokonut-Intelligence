"""Strategic positioning and segment value propositions."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_position(conn, strategy_plan_id: str, target_type: str, target_name: str, customer_needs: str, value_proposition: str, differentiation: str, *, landscape_id: Optional[str] = None, target_id: Optional[str] = None, value_drivers: Optional[List[Any]] = None, alternatives: Optional[List[Any]] = None, excluded_scope: Optional[str] = None, geographic_scope: Optional[str] = None, product_service_scope: Optional[str] = None, position_score: Optional[float] = None, confidence: str = "moderate", created_by_party_id: Optional[str] = None, visibility: str = "private") -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_position
            (strategy_plan_id, landscape_id, target_type, target_id, target_name, customer_needs,
             value_drivers, value_proposition, differentiation, alternatives, excluded_scope,
             geographic_scope, product_service_scope, position_score, confidence, created_by_party_id, visibility)
            VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::uuid, %s)
            RETURNING *""", (strategy_plan_id, landscape_id, target_type, target_id, target_name, customer_needs, json.dumps(value_drivers or []), value_proposition, differentiation, json.dumps(alternatives or []), excluded_scope, geographic_scope, product_service_scope, position_score, confidence, created_by_party_id, visibility))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def approve_position(conn, position_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_position SET status = 'approved', approved_by_party_id = %s::uuid,
            approved_at = NOW(), updated_at = NOW() WHERE id = %s::uuid AND status = 'submitted' RETURNING *""", (approved_by_party_id, position_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only submitted positions can be approved")
        conn.commit()
        return _clean(row)


def list_positions(conn, strategy_plan_id: str, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if status:
            cur.execute("SELECT * FROM strategy_position WHERE strategy_plan_id = %s::uuid AND status = %s ORDER BY target_name", (strategy_plan_id, status))
        else:
            cur.execute("SELECT * FROM strategy_position WHERE strategy_plan_id = %s::uuid ORDER BY target_name", (strategy_plan_id,))
        return [_clean(row) for row in cur.fetchall()]
