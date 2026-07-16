"""Bootstrap and inspect the dual-scope operating pilot."""

import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


BOUNDARIES = {
    "internal": {
        "key": "kokonut-internal-operations",
        "circle_key": "kokonut-operating-model",
        "name": "Kokonut Operating Model",
        "purpose": "Coordinate internal capacity, learning, delivery, and governance without exposing private personnel records.",
        "authority": "Internal role holders coordinate work and resource allocation; financial, legal, and publication decisions retain existing human approval gates.",
        "data": "Private personnel, capacity, coaching, and competency records remain internal and are exposed only as aggregates outside the scope.",
        "escalation": "Unresolved capacity, wellbeing, or authority tensions escalate to the operating governance circle and then to the existing governance proposal process.",
    },
    "adelphi": {
        "key": "kokonut-adelphi-field-operations",
        "circle_key": "adelphi-field-operations",
        "name": "Adelphi Field Operations",
        "purpose": "Coordinate farmer, ecological, market, and evidence work for the Kokonut Adelphi pilot.",
        "authority": "Farmers, field coordinators, ecological proxies, and stakeholder representatives retain domain authority; Kokonut provides bounded coordination and support.",
        "data": "Field, stakeholder, consent, ecological, and market records remain in their canonical governed domains; internal personnel data is not copied into field records.",
        "escalation": "Field harms, consent issues, ecological conflicts, and unresolved stakeholder concerns escalate through the Adelphi circle and existing grievance and governance workflows.",
    },
}


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def bootstrap(conn, internal_scope_id: str, adelphi_scope_id: str, *, approved_by_party_id: Optional[str] = None) -> List[Dict[str, Any]]:
    scopes = (("internal", internal_scope_id), ("adelphi", adelphi_scope_id))
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for scope_type, scope_id in scopes:
            config = BOUNDARIES[scope_type]
            cur.execute("""INSERT INTO governance_circle (circle_key, name, purpose, scope_type, scope_id, status, created_by_party_id)
                VALUES (%s, %s, %s, %s, %s::uuid, 'active', %s::uuid)
                ON CONFLICT (circle_key) DO UPDATE SET name = EXCLUDED.name, purpose = EXCLUDED.purpose, scope_id = EXCLUDED.scope_id
                RETURNING id""", (config["circle_key"], config["name"], config["purpose"], "organization" if scope_type == "internal" else "farm", scope_id, approved_by_party_id))
            circle_id = cur.fetchone()["id"]
            cur.execute("""INSERT INTO governance_role (circle_id, role_key, name, purpose, status, created_by_party_id)
                VALUES (%s::uuid, 'operating-coordinator', 'Operating Coordinator', 'Coordinate bounded work selection, capacity, and escalation.', 'active', %s::uuid)
                ON CONFLICT (circle_id, role_key) DO UPDATE SET purpose = EXCLUDED.purpose, status = 'active'""", (circle_id, approved_by_party_id))
            cur.execute("""INSERT INTO operating_pilot_scope
                (scope_type, scope_key, scope_id, governance_circle_id, authority_boundary, data_boundary, escalation_policy, status, approved_by_party_id, approved_at)
                VALUES (%s, %s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s::uuid, CASE WHEN %s::uuid IS NULL THEN NULL ELSE NOW() END)
                ON CONFLICT (scope_type) DO UPDATE SET scope_id = EXCLUDED.scope_id, governance_circle_id = EXCLUDED.governance_circle_id,
                    authority_boundary = EXCLUDED.authority_boundary, data_boundary = EXCLUDED.data_boundary,
                    escalation_policy = EXCLUDED.escalation_policy, status = EXCLUDED.status,
                    approved_by_party_id = EXCLUDED.approved_by_party_id, approved_at = EXCLUDED.approved_at
                RETURNING *""", (scope_type, config["key"], scope_id, circle_id, config["authority"], config["data"], config["escalation"], "active" if approved_by_party_id else "submitted", approved_by_party_id, approved_by_party_id))
        cur.execute("SELECT * FROM v_operating_pilot_registry ORDER BY scope_type")
        rows = [_clean(row) for row in cur.fetchall()]
        conn.commit()
        return rows


def registry(conn) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_operating_pilot_registry ORDER BY scope_type")
        return [_clean(row) for row in cur.fetchall()]
