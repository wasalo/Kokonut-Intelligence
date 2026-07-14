"""Shared helpers for governed enterprise-planning entities."""

from __future__ import annotations

import uuid
from typing import Mapping, Optional, Sequence, Set, Tuple

from psycopg2.extras import RealDictCursor

from services.common.logging import get_logger
from services.ingestion.base import get_db

logger = get_logger("planning.model")

PLAN_STATUSES = ("draft", "approved", "active", "closed", "cancelled")
OBJECTIVE_REVIEW_STATUSES = ("on_track", "at_risk", "off_track", "closed")
PROJECT_STATUSES = ("draft", "active", "on_hold", "done", "cancelled")


def _conn_or(conn):
    if conn is not None:
        return conn, False
    return get_db(), True


def allowed_transitions(spec, current_state: str) -> Set[str]:
    out: Set[str] = set()
    for step in spec.steps:
        if step.current_state == current_state:
            for transition in step.transitions:
                out.add(transition.next_state)
    return out


def all_states(spec) -> Set[str]:
    return {step.current_state for step in spec.steps} | {
        t.next_state for step in spec.steps for t in step.transitions
    }


def governed_transition(
    conn,
    table: str,
    row_id: str,
    to_status: str,
    spec,
    actor_type: str,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    note: Optional[str] = None,
    status_col: str = "status",
    id_col: str = "id",
) -> Mapping:
    """Validate and apply a lifecycle transition for a governed entity."""
    if to_status not in all_states(spec):
        raise ValueError(f"unknown status: {to_status}")
    conn2, own = _conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM {table} WHERE {id_col} = %s FOR UPDATE",
                (uuid.UUID(str(row_id)),),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"row not found in {table}: {row_id}")
            current = row[status_col]
            if to_status == current:
                raise ValueError(f"already in state {to_status}")
            if to_status not in allowed_transitions(spec, current):
                raise ValueError(f"cannot transition from {current} to {to_status}")
            cur.execute(
                f"UPDATE {table} SET {status_col} = %s, version = version + 1, updated_at = now() "
                f"WHERE {id_col} = %s RETURNING *",
                (to_status, uuid.UUID(str(row_id))),
            )
            updated = cur.fetchone()
            conn2.commit()
            logger.info("%s %s -> %s by %s", table, row_id, to_status, actor_type)
            return updated
    finally:
        if own:
            conn2.close()


def _row(conn, sql, params):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _rows(conn, sql, params):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()
