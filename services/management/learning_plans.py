"""Competency evidence and learning plans for role development."""

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def record_competency(conn, party_id: str, competency_key: str, current_level: float, *, target_level: float = 3, role_id: Optional[str] = None, evidence: Optional[List[Any]] = None, assessed_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if current_level < 0 or current_level > 5 or target_level < 0 or target_level > 5:
        raise ValueError("competency levels must be between 0 and 5")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO operating_competency_profile
            (party_id, governance_role_id, competency_key, current_level, target_level, evidence, assessed_by_party_id, assessed_at, status)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::uuid, CASE WHEN %s::uuid IS NULL THEN NULL ELSE NOW() END, 'submitted')
            ON CONFLICT (party_id, governance_role_id, competency_key) DO UPDATE SET
              current_level = EXCLUDED.current_level, target_level = EXCLUDED.target_level,
              evidence = EXCLUDED.evidence, assessed_by_party_id = EXCLUDED.assessed_by_party_id,
              assessed_at = EXCLUDED.assessed_at, status = 'submitted', updated_at = NOW()
            RETURNING *""", (party_id, role_id, competency_key, current_level, target_level, json.dumps(evidence or []), assessed_by_party_id, assessed_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def create_learning_plan(conn, party_id: str, scope_type: str, scope_id: str, title: str, *, competency_goals: Optional[List[Any]] = None, support_requested: Optional[List[Any]] = None, target_date: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if scope_type not in ("internal", "adelphi"):
        raise ValueError("scope_type must be internal or adelphi")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO operating_learning_plan
            (party_id, scope_type, scope_id, title, competency_goals, support_requested, target_date, created_by_party_id)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s::jsonb, %s::jsonb, %s, %s::uuid) RETURNING *""", (party_id, scope_type, scope_id, title, json.dumps(competency_goals or []), json.dumps(support_requested or []), target_date, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def list_gaps(conn, party_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if party_id:
            cur.execute("SELECT * FROM v_operating_competency_gaps WHERE party_id = %s::uuid ORDER BY gap_level DESC", (party_id,))
        else:
            cur.execute("SELECT * FROM v_operating_competency_gaps ORDER BY gap_level DESC")
        return [_clean(row) for row in cur.fetchall()]
