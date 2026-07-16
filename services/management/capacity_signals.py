"""Capacity and demand signals for the dual-scope operating model."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


SCOPES = ("internal", "adelphi")


def _uuid(value: Any) -> Any:
    return str(value) if isinstance(value, uuid.UUID) else value


def _rows(cur) -> List[Dict[str, Any]]:
    return [{key: _uuid(value) for key, value in dict(row).items()} for row in cur.fetchall()]


def record_capacity(
    conn, scope_type: str, scope_id: str, party_id: str,
    period_start: str, period_end: str, available_hours: float,
    *, committed_hours: float = 0, protected_hours: float = 0,
    source: str = "self_reported", notes: Optional[str] = None,
) -> Dict[str, Any]:
    if scope_type not in SCOPES:
        raise ValueError(f"scope_type must be one of {SCOPES}")
    if committed_hours + protected_hours > available_hours:
        raise ValueError("committed and protected hours cannot exceed available hours")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO operating_capacity_profile
               (scope_type, scope_id, party_id, period_start, period_end,
                available_hours, committed_hours, protected_hours, source, notes)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (scope_type, scope_id, party_id, period_start, period_end)
               WHERE status <> 'superseded'
               DO UPDATE SET available_hours = EXCLUDED.available_hours,
                   committed_hours = EXCLUDED.committed_hours,
                   protected_hours = EXCLUDED.protected_hours,
                   source = EXCLUDED.source, notes = EXCLUDED.notes,
                   updated_at = NOW()
               RETURNING *""",
            (scope_type, scope_id, party_id, period_start, period_end,
             available_hours, committed_hours, protected_hours, source, notes),
        )
        row = {key: _uuid(value) for key, value in dict(cur.fetchone()).items()}
        conn.commit()
        return row


def record_demand(
    conn, scope_type: str, scope_id: str, work_type: str,
    period_start: str, period_end: str, required_hours: float,
    *, priority: str = "medium", source: str = "planning",
    source_ref: Optional[str] = None, created_by_party_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    if scope_type not in SCOPES:
        raise ValueError(f"scope_type must be one of {SCOPES}")
    if required_hours < 0:
        raise ValueError("required_hours cannot be negative")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO operating_demand_signal
               (scope_type, scope_id, work_type, period_start, period_end,
                required_hours, priority, source, source_ref,
                created_by_party_id, description)
               VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid, %s::uuid, %s)
               RETURNING *""",
            (scope_type, scope_id, work_type, period_start, period_end,
             required_hours, priority, source, source_ref,
             created_by_party_id, description),
        )
        row = {key: _uuid(value) for key, value in dict(cur.fetchone()).items()}
        conn.commit()
        return row


def approve_capacity(conn, profile_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE operating_capacity_profile SET status = 'approved' WHERE id = %s::uuid RETURNING *", (profile_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("capacity profile not found")
        conn.commit()
        return {key: _uuid(value) for key, value in dict(row).items()}


def approve_demand(conn, signal_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE operating_demand_signal SET status = 'approved' WHERE id = %s::uuid RETURNING *", (signal_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("demand signal not found")
        conn.commit()
        return {key: _uuid(value) for key, value in dict(row).items()}


def list_gaps(conn, *, scope_type: Optional[str] = None, scope_id: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if scope_type:
        clauses.append("scope_type = %s")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = %s::uuid")
        params.append(scope_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_operating_capacity_gap{where} ORDER BY period_start, priority_rank DESC, work_type", params)
        return _rows(cur)
