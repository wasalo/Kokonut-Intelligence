"""Work item workbench: create, assign, transition, and SLA sweeps.

The work-item lifecycle is governed by the ``work_item`` workflow specification
(see ``services/workflow_specs/work_item.py``). Service transitions are validated
against that single source of truth so the database, the spec, and the runtime
cannot drift apart.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional, Sequence

from psycopg2.extras import RealDictCursor

from services.common.logging import get_logger
from services.ingestion.base import get_db
from services.management.model import TERMINAL_STATES
from services.workflow_specs.work_item import WORK_ITEM

logger = get_logger("management.workbench")

ALL_STATES = set(WORK_ITEM.states)


def allowed_transitions(current_state: str) -> set:
    """Return the set of next states permitted from ``current_state``."""
    out: set = set()
    for step in WORK_ITEM.steps:
        if step.current_state == current_state:
            for transition in step.transitions:
                out.add(transition.next_state)
    return out


def _conn_or(conn):
    if conn is not None:
        return conn, False
    return get_db(), True


def _row(conn, sql, params):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _rows(conn, sql, params):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def get_work_item(conn, work_item_id: str) -> Optional[Mapping]:
    """Return a single work item or ``None``."""
    return _row(
        conn,
        "SELECT * FROM work_item WHERE id = %s",
        (uuid.UUID(work_item_id),),
    )


def list_work_items(
    conn,
    organization_id: str,
    status: Optional[str] = None,
    assignee_type: Optional[str] = None,
    assignee_id: Optional[str] = None,
) -> Sequence[Mapping]:
    """List work items for an organization with optional filters."""
    clauses = ["organization_id = %s"]
    params: list = [uuid.UUID(organization_id)]
    if status:
        clauses.append("status = %s")
        params.append(status)
    if assignee_type:
        clauses.append("assignee_type = %s")
        params.append(assignee_type)
        if assignee_id:
            clauses.append("assignee_id = %s")
            params.append(uuid.UUID(assignee_id))
    return _rows(
        conn,
        f"SELECT * FROM work_item WHERE {' AND '.join(clauses)} ORDER BY created_at DESC",
        tuple(params),
    )


def create_work_item(
    conn,
    organization_id: str,
    title: str,
    created_by_type: str,
    created_by_id: Optional[str] = None,
    description: Optional[str] = None,
    priority: str = "medium",
    assignee_type: Optional[str] = None,
    assignee_id: Optional[str] = None,
    location_id: Optional[str] = None,
    parent_work_item_id: Optional[str] = None,
    due_at: Optional[str] = None,
    sla_at: Optional[str] = None,
):
    """Create a work item in ``draft`` (or ``assigned`` when an owner is given)."""
    initial_status = "assigned" if assignee_id else "draft"
    conn2, own = _conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO work_item (
                    organization_id, title, description, status, priority,
                    assignee_type, assignee_id, created_by_type, created_by_id,
                    location_id, parent_work_item_id, due_at, sla_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    uuid.UUID(organization_id), title, description, initial_status, priority,
                    assignee_type, uuid.UUID(assignee_id) if assignee_id else None,
                    created_by_type, uuid.UUID(created_by_id) if created_by_id else None,
                    uuid.UUID(location_id) if location_id else None,
                    uuid.UUID(parent_work_item_id) if parent_work_item_id else None,
                    _parse_ts(due_at), _parse_ts(sla_at),
                ),
            )
            row = cur.fetchone()
            _record_event(
                conn2, row["id"], row["status"], row["status"], "create",
                created_by_type, created_by_id, "Work item created",
            )
            conn2.commit()
            return row
    finally:
        if own:
            conn2.close()


def assign(
    conn,
    work_item_id: str,
    assignee_type: str,
    assignee_id: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    note: Optional[str] = None,
):
    """Assign (or reassign) an owner. Drives draft -> assigned."""
    conn2, own = _conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM work_item WHERE id = %s FOR UPDATE", (uuid.UUID(work_item_id),))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"work item not found: {work_item_id}")
            current = row["status"]
            if current not in ("draft", "assigned"):
                raise ValueError(f"cannot assign from state {current}")
            new_status = "assigned" if current == "draft" else current
            cur.execute(
                """
                UPDATE work_item
                SET assignee_type = %s, assignee_id = %s, status = %s,
                    version = version + 1, updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (assignee_type, uuid.UUID(assignee_id), new_status, uuid.UUID(work_item_id)),
            )
            updated = cur.fetchone()
            _record_event(
                conn2, updated["id"], current, updated["status"], "assign",
                actor_type, actor_id, note or "Owner assigned",
            )
            conn2.commit()
            return updated
    finally:
        if own:
            conn2.close()


def transition(
    conn,
    work_item_id: str,
    to_status: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    note: Optional[str] = None,
):
    """Transition a work item to ``to_status``, validating against the spec."""
    if to_status not in ALL_STATES:
        raise ValueError(f"unknown status: {to_status}")
    conn2, own = _conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM work_item WHERE id = %s FOR UPDATE", (uuid.UUID(work_item_id),))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"work item not found: {work_item_id}")
            current = row["status"]
            if to_status == current:
                raise ValueError(f"work item already in state {to_status}")
            if to_status not in allowed_transitions(current):
                raise ValueError(f"cannot transition from {current} to {to_status}")
            if to_status == "blocked" and not note:
                raise ValueError("blocked requires a reason note")
            if to_status == "assigned" and not row["assignee_id"]:
                raise ValueError("cannot assign without an owner")
            started_at = row["started_at"]
            completed_at = row["completed_at"]
            cancelled_at = row["cancelled_at"]
            now = datetime.now(timezone.utc)
            if to_status == "in_progress" and not started_at:
                started_at = now
            if to_status == "done":
                completed_at = now
            if to_status == "cancelled":
                cancelled_at = now
            cur.execute(
                """
                UPDATE work_item
                SET status = %s, started_at = %s, completed_at = %s, cancelled_at = %s,
                    version = version + 1, updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (to_status, started_at, completed_at, cancelled_at, uuid.UUID(work_item_id)),
            )
            updated = cur.fetchone()
            _record_event(
                conn2, updated["id"], current, updated["status"], action or "transition",
                actor_type, actor_id, note,
            )
            conn2.commit()
            return updated
    finally:
        if own:
            conn2.close()


def check_sla(conn, organization_id: Optional[str] = None) -> Mapping:
    """Passively return overdue and SLA-breached open items (no mutation)."""
    clause = "status NOT IN ('done', 'cancelled')"
    params: list = []
    if organization_id:
        clause += " AND organization_id = %s"
        params.append(uuid.UUID(organization_id))
    now = datetime.now(timezone.utc)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"SELECT * FROM work_item WHERE {clause} AND due_at < %s ORDER BY due_at",
            tuple(params + [now]),
        )
        overdue = cur.fetchall()
        cur.execute(
            f"SELECT * FROM work_item WHERE {clause} AND sla_at < %s ORDER BY sla_at",
            tuple(params + [now]),
        )
        breached = cur.fetchall()
    return {"overdue": overdue, "breached": breached}


def _record_event(conn, work_item_id, from_status, to_status, action, actor_type, actor_id, note):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_item_event (
                work_item_id, actor_type, actor_id, from_status, to_status, action, note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid.UUID(str(work_item_id)), actor_type,
                uuid.UUID(actor_id) if actor_id else None,
                from_status, to_status, action, note,
            ),
        )


def _parse_ts(value: Optional[str]):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
