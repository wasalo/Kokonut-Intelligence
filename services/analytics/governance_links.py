"""Cross-circle representative and liaison link services."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


LINK_TYPES = ("lead_link", "representative_link", "liaison", "observer")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def create_link(
    conn,
    source_circle_id: str,
    target_circle_id: str,
    link_type: str,
    role_id: str,
    party_id: str,
    mandate: str,
    *,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    term_start: Optional[datetime] = None,
    term_end: Optional[datetime] = None,
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if link_type not in LINK_TYPES:
        raise ValueError(f"link_type must be one of {LINK_TYPES}")
    if not mandate.strip():
        raise ValueError("mandate is required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO governance_circle_link
               (source_circle_id, target_circle_id, link_type, role_id, party_id,
                mandate, scope_type, scope_id, term_start, term_end, evidence)
               VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s::uuid, %s, %s,
                       %s::uuid, COALESCE(%s, NOW()), %s, %s::jsonb)
               RETURNING *""",
            (source_circle_id, target_circle_id, link_type, role_id, party_id,
             mandate, scope_type, scope_id, term_start, term_end,
             json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def approve_link(conn, link_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE governance_circle_link
               SET status = 'active', approved_by_party_id = %s::uuid,
                   approved_at = NOW(), updated_at = NOW()
               WHERE id = %s::uuid RETURNING *""",
            (approved_by_party_id, link_id),
        )
        result = _row(cur.fetchone())
        if not result:
            conn.rollback()
            raise ValueError("circle link not found")
        conn.commit()
        return result


def end_link(conn, link_id: str, *, recused: bool = False) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE governance_circle_link
               SET status = CASE WHEN %s THEN 'suspended' ELSE 'ended' END,
                   recusal_status = CASE WHEN %s THEN 'recused' ELSE recusal_status END,
                   term_end = COALESCE(term_end, NOW()), updated_at = NOW()
               WHERE id = %s::uuid RETURNING *""",
            (recused, recused, link_id),
        )
        result = _row(cur.fetchone())
        if not result:
            conn.rollback()
            raise ValueError("circle link not found")
        conn.commit()
        return result


def list_links(conn, *, source_circle_id: Optional[str] = None, target_circle_id: Optional[str] = None, party_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    for column, value in (("source_circle_id", source_circle_id), ("target_circle_id", target_circle_id), ("party_id", party_id)):
        if value:
            clauses.append(f"{column} = %s::uuid")
            params.append(value)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_governance_circle_links{where} ORDER BY term_end NULLS LAST, source_circle_key", params)
        return [_row(row) for row in cur.fetchall()]
