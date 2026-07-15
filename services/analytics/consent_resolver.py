"""Canonical, conservative stakeholder consent resolver."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


SCOPE_TYPES = (
    "network", "organization", "location", "farm", "cooperative",
    "value_stream", "initiative", "decision",
)
EVENT_TYPES = ("grant", "withdraw", "deny", "expire")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def record_consent(
    conn,
    party_id: str,
    data_category: str,
    purpose: str,
    *,
    event_type: str = "grant",
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    recipient_party_id: Optional[str] = None,
    recipient_type: str = "system",
    recipient_name: Optional[str] = None,
    consent_method: str = "digital_form",
    legal_basis: str = "consent",
    consent_version: str = "1.0",
    effective_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    reason: Optional[str] = None,
    evidence: Optional[List[Any]] = None,
    source_system: str = "stakeholder_registry",
    source_record_id: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type must be one of {EVENT_TYPES}")
    if scope_type not in SCOPE_TYPES:
        raise ValueError(f"scope_type must be one of {SCOPE_TYPES}")
    if not data_category.strip() or not purpose.strip():
        raise ValueError("data_category and purpose are required")
    if event_type != "grant" and not (reason or "").strip():
        raise ValueError("reason is required when consent is not granted")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_consent
               (party_id, event_type, data_category, purpose, scope_type, scope_id,
                recipient_party_id, recipient_type, recipient_name, consent_method,
                legal_basis, consent_version, effective_at, expires_at, reason, evidence,
                source_system, source_record_id, created_by)
               VALUES (%s::uuid, %s, %s, %s, %s, %s::uuid, %s::uuid, %s, %s, %s,
                       %s, %s, COALESCE(%s, NOW()), %s, %s, %s::jsonb, %s, %s, %s::uuid)
               RETURNING *""",
            (party_id, event_type, data_category, purpose, scope_type, scope_id,
             recipient_party_id, recipient_type, recipient_name, consent_method,
             legal_basis, consent_version, effective_at, expires_at, reason, json.dumps(evidence or []),
             source_system, source_record_id, created_by),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def check_consent(
    conn,
    party_id: str,
    data_category: str,
    purpose: str,
    *,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    recipient_party_id: Optional[str] = None,
    recipient_type: str = "system",
) -> Dict[str, Any]:
    """Return the effective decision; missing records deny access."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT * FROM v_effective_stakeholder_consent
               WHERE party_id = %s::uuid
                 AND data_category = %s
                 AND purpose = %s
                 AND scope_type = %s
                 AND scope_id IS NOT DISTINCT FROM %s::uuid
                 AND recipient_party_id IS NOT DISTINCT FROM %s::uuid
                 AND recipient_type = %s
               LIMIT 1""",
            (party_id, data_category, purpose, scope_type, scope_id,
             recipient_party_id, recipient_type),
        )
        result = _row(cur.fetchone())
    if result:
        return result
    return {
        "party_id": party_id,
        "data_category": data_category,
        "purpose": purpose,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "recipient_party_id": recipient_party_id,
        "recipient_type": recipient_type,
        "effective_status": "absent",
        "consented": False,
        "reason": "No explicit consent decision exists",
    }


def list_effective_consent(
    conn,
    party_id: Optional[str] = None,
    *,
    effective_status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if party_id:
        clauses.append("party_id = %s::uuid")
        params.append(party_id)
    if effective_status:
        clauses.append("effective_status = %s")
        params.append(effective_status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_effective_stakeholder_consent{where} ORDER BY party_name, data_category, purpose", params)
        return [_row(row) for row in cur.fetchall()]


def withdraw_consent(conn, consent_event_id: str, reason: str, *, created_by: Optional[str] = None) -> Dict[str, Any]:
    if not reason.strip():
        raise ValueError("withdrawal reason is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT party_id, data_category, purpose, scope_type, scope_id,
                      recipient_party_id, recipient_type, recipient_name,
                      consent_method, legal_basis, consent_version
               FROM stakeholder_consent WHERE id = %s::uuid""",
            (consent_event_id,),
        )
        source = cur.fetchone()
    if not source:
        return {"error": "consent event not found", "consent_event_id": consent_event_id}
    return record_consent(
        conn, source["party_id"], source["data_category"], source["purpose"],
        event_type="withdraw", scope_type=source["scope_type"], scope_id=source["scope_id"],
        recipient_party_id=source["recipient_party_id"], recipient_type=source["recipient_type"],
        recipient_name=source["recipient_name"], consent_method=source["consent_method"],
        legal_basis=source["legal_basis"], consent_version=source["consent_version"],
        reason=reason, source_system="consent_resolver", source_record_id=consent_event_id,
        created_by=created_by,
    )
