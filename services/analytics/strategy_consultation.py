"""Consultation and communication workflows for strategy plans."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_consultation(conn, strategy_plan_id: str, title: str, prompt: str, audience_type: str, *, audience_scope_id: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_consultation
            (strategy_plan_id, title, prompt, audience_type, audience_scope_id, created_by_party_id)
            VALUES (%s::uuid, %s, %s, %s, %s::uuid, %s::uuid) RETURNING *""", (strategy_plan_id, title, prompt, audience_type, audience_scope_id, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def open_consultation(conn, consultation_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE strategy_consultation SET status = 'open', opens_at = COALESCE(opens_at, NOW()) WHERE id = %s::uuid AND status = 'draft' RETURNING *", (consultation_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only draft consultations can be opened")
        conn.commit()
        return _clean(row)


def submit_response(conn, consultation_id: str, response: str, *, respondent_party_id: Optional[str] = None, consent_checked: bool = False) -> Dict[str, Any]:
    if not consent_checked:
        raise ValueError("consultation response requires consent confirmation")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_consultation_response
            (consultation_id, respondent_party_id, response, consent_checked)
            SELECT %s::uuid, %s::uuid, %s, TRUE
            WHERE EXISTS (SELECT 1 FROM strategy_consultation WHERE id = %s::uuid AND status = 'open')
            RETURNING *""", (consultation_id, respondent_party_id, response, consultation_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("consultation is not open")
        conn.commit()
        return _clean(row)


def synthesize_consultation(conn, consultation_id: str, *, include_count: Optional[int] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_consultation SET status = 'synthesized', synthesis = jsonb_build_object(
            'response_count', (SELECT COUNT(*) FROM strategy_consultation_response WHERE consultation_id = %s::uuid AND status = 'submitted'),
            'included_count', (SELECT COUNT(*) FROM strategy_consultation_response WHERE consultation_id = %s::uuid AND status = 'included'),
            'private_by_default', TRUE,
            'included_by_human', %s
        ) WHERE id = %s::uuid AND status IN ('open', 'closed') RETURNING *""", (consultation_id, consultation_id, include_count, consultation_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only open or closed consultations can be synthesized")
        conn.commit()
        return _clean(row)


def create_communication(conn, strategy_plan_id: str, message: str, audience_type: str, channel: str, *, subject: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_communication
            (strategy_plan_id, audience_type, channel, subject, message, created_by_party_id)
            VALUES (%s::uuid, %s, %s, %s, %s, %s::uuid) RETURNING *""", (strategy_plan_id, audience_type, channel, subject, message, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def publish_communication(conn, communication_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_communication SET status = 'published', approved_by_party_id = %s::uuid,
            approved_at = NOW(), published_at = NOW()
            WHERE id = %s::uuid AND status = 'draft' RETURNING *""", (approved_by_party_id, communication_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only draft communications can be published with human approval")
        conn.commit()
        return _clean(row)
