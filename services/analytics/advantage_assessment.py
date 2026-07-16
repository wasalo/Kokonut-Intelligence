"""VRIO-style defensible advantage assessments."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


SCORE_FIELDS = ("valuable_score", "rare_score", "inimitable_score", "organized_score", "switching_cost_score", "network_effect_score", "evidence_advantage_score", "ecological_score", "social_score", "governance_trust_score")


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_advantage(conn, strategy_plan_id: str, name: str, statement: str, *, position_id: Optional[str] = None, owner_party_id: Optional[str] = None, evidence: Optional[List[Any]] = None, **scores) -> Dict[str, Any]:
    values = [scores.get(field, 0) for field in SCORE_FIELDS]
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_advantage
            (strategy_plan_id, position_id, name, statement, valuable_score, rare_score, inimitable_score, organized_score,
             switching_cost_score, network_effect_score, evidence_advantage_score, ecological_score, social_score, governance_trust_score,
             evidence, owner_party_id)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::uuid)
            RETURNING *""", [strategy_plan_id, position_id, name, statement] + values + [json.dumps(evidence or []), owner_party_id])
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def assess_advantage(conn, advantage_id: str, assessed_by_party_id: str, *, imitation_risk: str = "unknown", capture_risk: str = "unknown") -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM strategy_advantage WHERE id = %s::uuid FOR UPDATE", (advantage_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("advantage not found")
        vrio = sum(float(row[field] or 0) for field in ("valuable_score", "rare_score", "inimitable_score", "organized_score")) / 4
        reinforcing = sum(float(row[field] or 0) for field in ("switching_cost_score", "network_effect_score", "evidence_advantage_score", "ecological_score", "social_score", "governance_trust_score")) / 6
        defensibility = round(vrio * 0.65 + reinforcing * 0.35, 2)
        cur.execute("""UPDATE strategy_advantage SET defensibility_score = %s, imitation_risk = %s,
            capture_risk = %s, status = 'verified', assessed_at = NOW(), assessed_by_party_id = %s::uuid, updated_at = NOW()
            WHERE id = %s::uuid RETURNING *""", (defensibility, imitation_risk, capture_risk, assessed_by_party_id, advantage_id))
        result = _clean(cur.fetchone())
        conn.commit()
        return result


def list_advantages(conn, strategy_plan_id: str, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if status:
            cur.execute("SELECT * FROM strategy_advantage WHERE strategy_plan_id = %s::uuid AND status = %s ORDER BY defensibility_score DESC NULLS LAST", (strategy_plan_id, status))
        else:
            cur.execute("SELECT * FROM strategy_advantage WHERE strategy_plan_id = %s::uuid ORDER BY defensibility_score DESC NULLS LAST", (strategy_plan_id,))
        return [_clean(row) for row in cur.fetchall()]
