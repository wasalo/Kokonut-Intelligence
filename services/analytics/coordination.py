"""Governed coordination strategy service.

Coordination records describe commitments and learning between parties. They
do not create legal ownership, authorize spending, or activate operations.
Those transitions require an explicit human actor.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db


def _conn():
    return get_db()


def _row(row: Optional[psycopg2.extras.RealDictRow]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, (datetime, date, uuid_mod.UUID)):
            result[key] = str(value)
    return result


def _insert(table: str, values: Dict[str, Any]) -> Dict[str, Any]:
    record_id = str(uuid_mod.uuid4())
    values = {"id": record_id, **values}
    columns = list(values)
    placeholders = ["%s::jsonb" if column in {"evidence", "metadata"} else "%s" for column in columns]
    params = [json.dumps(values[column]) if column in {"evidence", "metadata"} else values[column] for column in columns]
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING *",
                params,
            )
            conn.commit()
            return _row(cur.fetchone()) or {}


def create_alliance(
    name: str,
    purpose: str,
    *,
    coordination_type: str = "alliance",
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    strategy_map_id: Optional[str] = None,
    value_stream_id: Optional[str] = None,
    stakeholder_decision_id: Optional[str] = None,
    cooperative_proposal_id: Optional[str] = None,
    steward_party_id: Optional[str] = None,
    market_cycle: str = "standard",
    work_item_id: Optional[str] = None,
    proxy_authority_id: Optional[str] = None,
    review_due_at: Optional[str] = None,
    approval_quorum_required: int = 1,
    created_by_party_id: Optional[str] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return _insert("coordination_alliance", {
        "name": name, "purpose": purpose, "coordination_type": coordination_type,
        "scope_type": scope_type, "scope_id": scope_id, "strategy_map_id": strategy_map_id,
        "value_stream_id": value_stream_id, "steward_party_id": steward_party_id,
        "stakeholder_decision_id": stakeholder_decision_id,
        "cooperative_proposal_id": cooperative_proposal_id,
        "market_cycle": market_cycle, "work_item_id": work_item_id,
        "proxy_authority_id": proxy_authority_id, "review_due_at": review_due_at,
        "approval_quorum_required": approval_quorum_required,
        "created_by_party_id": created_by_party_id, "evidence": evidence or [],
    })


def list_alliances(*, status: Optional[str] = None, coordination_type: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if coordination_type:
        clauses.append("coordination_type = %s")
        params.append(coordination_type)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM coordination_alliance{where} ORDER BY created_at DESC", params)
            return [_row(row) or {} for row in cur.fetchall()]


def approve_alliance(alliance_id: str, approved_by_party_id: str, approval_basis: str) -> Dict[str, Any]:
    if not approval_basis.strip():
        raise ValueError("approval_basis is required")
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO coordination_approval (alliance_id, party_id, basis)
                   VALUES (%s::uuid, %s::uuid, %s)
                   ON CONFLICT (alliance_id, party_id) DO UPDATE
                   SET approval_status = 'approved', basis = EXCLUDED.basis,
                       created_at = NOW()""",
                (alliance_id, approved_by_party_id, approval_basis),
            )
            cur.execute(
                "UPDATE coordination_alliance SET status = 'approved', approved_by_party_id = %s::uuid, "
                "approved_at = NOW(), approval_basis = %s "
                "WHERE id = %s::uuid AND status IN ('draft', 'proposed') "
                "AND (SELECT COUNT(*) FROM coordination_approval WHERE alliance_id = coordination_alliance.id AND approval_status = 'approved') >= approval_quorum_required "
                "RETURNING *",
                (approved_by_party_id, approval_basis, alliance_id),
            )
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT * FROM coordination_alliance WHERE id = %s::uuid", (alliance_id,))
                row = cur.fetchone()
                if row and row["status"] == "draft":
                    cur.execute(
                        "UPDATE coordination_alliance SET status = 'proposed' WHERE id = %s::uuid RETURNING *",
                        (alliance_id,),
                    )
                    row = cur.fetchone()
            conn.commit()
            if not row:
                raise ValueError("alliance not found")
            return _row(row) or {}


def activate_alliance(alliance_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE coordination_alliance SET status = 'active', starts_at = COALESCE(starts_at, NOW()) "
                "WHERE id = %s::uuid AND approved_by_party_id = %s::uuid AND status = 'approved' RETURNING *",
                (alliance_id, approved_by_party_id),
            )
            row = cur.fetchone()
            conn.commit()
            if not row:
                raise ValueError("alliance must be approved by the activating reviewer")
            return _row(row) or {}


def add_participant(alliance_id: str, party_id: str, *, role: str = "participant", consent_event_id: Optional[str] = None,
                    contribution_expectation: Optional[str] = None, benefit_expectation: Optional[str] = None) -> Dict[str, Any]:
    return _insert("coordination_participant", {
        "alliance_id": alliance_id, "party_id": party_id, "role": role,
        "consent_event_id": consent_event_id, "contribution_expectation": contribution_expectation,
        "benefit_expectation": benefit_expectation,
    })


def activate_participant(participant_id: str, consent_event_id: str) -> Dict[str, Any]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE coordination_participant SET status = 'active', consent_event_id = %s::uuid "
                "WHERE id = %s::uuid RETURNING *", (consent_event_id, participant_id),
            )
            row = cur.fetchone()
            conn.commit()
            if not row:
                raise ValueError("participant not found")
            return _row(row) or {}


def add_objective(alliance_id: str, title: str, description: str, objective_type: str, *,
                  target_value: Optional[float] = None, target_unit: Optional[str] = None,
                  harm_if_missed: Optional[str] = None) -> Dict[str, Any]:
    return _insert("coordination_objective", {
        "alliance_id": alliance_id, "title": title, "description": description,
        "objective_type": objective_type, "target_value": target_value,
        "target_unit": target_unit, "harm_if_missed": harm_if_missed,
    })


def add_contribution(alliance_id: str, participant_id: str, contribution_type: str, description: str, *,
                     committed_value: Optional[float] = None, value_unit: Optional[str] = None,
                     idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    values = {
        "alliance_id": alliance_id, "participant_id": participant_id,
        "contribution_type": contribution_type, "description": description,
        "committed_value": committed_value, "value_unit": value_unit,
        "idempotency_key": idempotency_key,
    }
    return _insert_idempotent("coordination_contribution", values)


def add_benefit(alliance_id: str, description: str, benefit_type: str, *, participant_id: Optional[str] = None,
                expected_value: Optional[float] = None, value_unit: Optional[str] = None,
                idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    values = {
        "alliance_id": alliance_id, "participant_id": participant_id,
        "benefit_type": benefit_type, "description": description,
        "expected_value": expected_value, "value_unit": value_unit,
        "idempotency_key": idempotency_key,
    }
    return _insert_idempotent("coordination_benefit", values)


def _insert_idempotent(table: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a coordination record once when a caller supplies an idempotency key."""
    record_id = str(uuid_mod.uuid4())
    values = {"id": record_id, **values}
    columns = list(values)
    placeholders = ["%s::jsonb" if column in {"evidence", "metadata"} else "%s" for column in columns]
    params = [json.dumps(values[column]) if column in {"evidence", "metadata"} else values[column] for column in columns]
    if values.get("idempotency_key") is None:
        return _insert(table, {key: value for key, value in values.items() if key != "id"})
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) "
            "ON CONFLICT (alliance_id, idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING "
            "RETURNING *",
            params,
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                f"SELECT * FROM {table} WHERE alliance_id = %s::uuid AND idempotency_key = %s",
                (values["alliance_id"], values["idempotency_key"]),
            )
            row = cur.fetchone()
        conn.commit()
        return _row(row) or {}


def configure_fast_pilot(alliance_id: str, rollback_plan: str, reversible_until: str) -> Dict[str, Any]:
    if not rollback_plan.strip() or not reversible_until:
        raise ValueError("rollback_plan and reversible_until are required")
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE coordination_alliance
               SET metadata = metadata || jsonb_build_object(
                   'reversible_pilot', jsonb_build_object('rollback_plan', %s)),
                   reversible_until = %s::timestamptz
               WHERE id = %s::uuid AND market_cycle = 'fast'
               RETURNING *""",
            (rollback_plan, reversible_until, alliance_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("only fast-cycle alliances can be configured as reversible pilots")
        return _row(row) or {}


def link_shared_procurement(alliance_id: str, procurement_order_id: str) -> Dict[str, Any]:
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT status FROM collective_market_order WHERE id = %s::uuid", (procurement_order_id,))
        order = cur.fetchone()
        if not order or order["status"] in {"completed", "cancelled"}:
            raise ValueError("shared procurement order must exist and remain open")
        cur.execute(
            """UPDATE coordination_alliance SET shared_procurement_order_id = %s::uuid
               WHERE id = %s::uuid AND market_cycle = 'standard' RETURNING *""",
            (procurement_order_id, alliance_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("shared procurement is only available for standard-cycle alliances")
        return _row(row) or {}


def add_risk(alliance_id: str, risk_type: str, description: str, *, likelihood: Optional[float] = None,
             impact: Optional[float] = None, mitigation: Optional[str] = None,
             owner_party_id: Optional[str] = None) -> Dict[str, Any]:
    return _insert("coordination_risk", {
        "alliance_id": alliance_id, "risk_type": risk_type, "description": description,
        "likelihood": likelihood, "impact": impact, "mitigation": mitigation,
        "owner_party_id": owner_party_id,
    })


def add_knowledge_exchange(alliance_id: str, from_party_id: str, topic: str, exchange_type: str, *,
                           to_party_id: Optional[str] = None, artifact_uri: Optional[str] = None,
                           consent_scope: Optional[str] = None, consent_event_id: Optional[str] = None) -> Dict[str, Any]:
    return _insert("coordination_knowledge_exchange", {
        "alliance_id": alliance_id, "from_party_id": from_party_id, "to_party_id": to_party_id,
        "topic": topic, "exchange_type": exchange_type, "artifact_uri": artifact_uri,
        "consent_scope": consent_scope, "consent_event_id": consent_event_id,
    })


def get_coordination_health(alliance_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM v_coordination_health"
    params: List[Any] = []
    if alliance_id:
        query += " WHERE alliance_id = %s::uuid"
        params.append(alliance_id)
    query += " ORDER BY name"
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [_row(row) or {} for row in cur.fetchall()]
