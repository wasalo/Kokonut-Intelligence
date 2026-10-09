"""Governance links and approval-route checks for strategy plans."""

import uuid
from typing import Any, Dict, List

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def add_link(conn, strategy_plan_id: str, record_type: str, record_id: str, relationship: str, *, required: bool = False, note: str = "", created_by_party_id: str = None) -> Dict[str, Any]:
    validate_link(conn, strategy_plan_id, record_type, record_id)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_governance_link
            (strategy_plan_id, record_type, record_id, relationship, required, note, created_by_party_id)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s::uuid)
            ON CONFLICT (strategy_plan_id, record_type, record_id, relationship) DO UPDATE SET
              required = EXCLUDED.required, note = EXCLUDED.note,
              status = CASE WHEN strategy_governance_link.status = 'approved' THEN 'approved' ELSE 'linked' END
            RETURNING *""", (strategy_plan_id, record_type, record_id, relationship, required, note, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def validate_link(conn, strategy_plan_id: str, record_type: str, record_id: str) -> None:
    if record_type not in ("governance_circle", "stakeholder_decision", "governance_proposal", "stakeholder_grievance"):
        raise ValueError("invalid governance record type")
    if record_type in ("governance_proposal", "stakeholder_grievance"):
        return
    with conn.cursor() as cur:
        cur.execute("SELECT scope_type, scope_id FROM strategy_plan WHERE id = %s::uuid", (strategy_plan_id,))
        plan = cur.fetchone()
        if not plan:
            raise ValueError("strategy plan not found")
        table = "governance_circle" if record_type == "governance_circle" else "stakeholder_decision"
        cur.execute(f"SELECT scope_type, scope_id FROM {table} WHERE id = %s::uuid", (record_id,))
        record = cur.fetchone()
        if not record:
            raise ValueError("governance record not found")
        if record[1] is not None and record[1] != plan[1]:
            raise ValueError("governance record is outside strategy plan scope")
        allowed = {"organization": {"organization", "network"}, "location": {"location", "farm", "network"}}[plan[0]]
        if record[0] not in allowed:
            raise ValueError("governance record scope is incompatible with strategy plan")


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
