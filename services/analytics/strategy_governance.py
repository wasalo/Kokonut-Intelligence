"""Governance links and approval-route checks for strategy plans."""

import uuid
from typing import Any, Dict, List

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def add_link(conn, strategy_plan_id: str, record_type: str, record_id: str, relationship: str, *, required: bool = False, note: str = "", created_by_party_id: str = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_governance_link
            (strategy_plan_id, record_type, record_id, relationship, required, note, created_by_party_id)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s::uuid)
            ON CONFLICT (strategy_plan_id, record_type, record_id, relationship) DO UPDATE SET
              required = EXCLUDED.required, note = EXCLUDED.note, status = 'linked'
            RETURNING *""", (strategy_plan_id, record_type, record_id, relationship, required, note, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def list_links(conn, strategy_plan_id: str, *, relationship: str = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if relationship:
            cur.execute("SELECT * FROM strategy_governance_link WHERE strategy_plan_id = %s::uuid AND relationship = %s ORDER BY created_at", (strategy_plan_id, relationship))
        else:
            cur.execute("SELECT * FROM strategy_governance_link WHERE strategy_plan_id = %s::uuid ORDER BY created_at", (strategy_plan_id,))
        return [_clean(row) for row in cur.fetchall()]


def approval_route_satisfied(conn, strategy_plan_id: str, approval_mode: str) -> bool:
    required_types = {
        "governance_circle": {"governance_circle"},
        "stakeholder_decision": {"stakeholder_decision"},
        "dual": {"governance_circle", "stakeholder_decision"},
    }.get(approval_mode)
    if required_types is None:
        raise ValueError("invalid approval mode")
    with conn.cursor() as cur:
        cur.execute("""SELECT DISTINCT record_type FROM strategy_governance_link
            WHERE strategy_plan_id = %s::uuid AND relationship = 'approval' AND status = 'approved'""", (strategy_plan_id,))
        return required_types.issubset({row[0] for row in cur.fetchall()})
