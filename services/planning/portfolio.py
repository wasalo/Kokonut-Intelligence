"""Program / project portfolio (PPM) service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence

from psycopg2.extras import RealDictCursor

from services.common.logging import get_logger
from services.ingestion.base import get_db
from services.planning import model
from services.workflow_specs.project import PROJECT

logger = get_logger("planning.portfolio")


def create_program(
    conn,
    organization_id: str,
    name: str,
    objective_id: Optional[str] = None,
    budget_id: Optional[str] = None,
    created_by_type: str = "system",
    created_by_id: Optional[str] = None,
) -> Mapping:
    conn2, own = model._conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO program (organization_id, name, objective_id, budget_id, created_by_type, created_by_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (uuid.UUID(organization_id), name,
                 uuid.UUID(objective_id) if objective_id else None,
                 uuid.UUID(budget_id) if budget_id else None,
                 created_by_type, uuid.UUID(created_by_id) if created_by_id else None),
            )
            row = cur.fetchone()
            conn2.commit()
            return row
    finally:
        if own:
            conn2.close()


def create_project(
    conn,
    organization_id: str,
    name: str,
    program_id: Optional[str] = None,
    objective_id: Optional[str] = None,
    budget_id: Optional[str] = None,
    due_at: Optional[str] = None,
) -> Mapping:
    conn2, own = model._conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO project (program_id, organization_id, name, objective_id, budget_id, due_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (uuid.UUID(program_id) if program_id else None, uuid.UUID(organization_id), name,
                 uuid.UUID(objective_id) if objective_id else None,
                 uuid.UUID(budget_id) if budget_id else None, _as_ts(due_at)),
            )
            row = cur.fetchone()
            conn2.commit()
            return row
    finally:
        if own:
            conn2.close()


def get_program(conn, program_id: str) -> Optional[Mapping]:
    return model._row(conn, "SELECT * FROM program WHERE id = %s", (uuid.UUID(program_id),))


def get_project(conn, project_id: str) -> Optional[Mapping]:
    return model._row(conn, "SELECT * FROM project WHERE id = %s", (uuid.UUID(project_id),))


def list_programs(conn, organization_id: str, status: Optional[str] = None) -> Sequence[Mapping]:
    clauses = ["organization_id = %s"]
    params: list = [uuid.UUID(organization_id)]
    if status:
        clauses.append("status = %s")
        params.append(status)
    return model._rows(conn, f"SELECT * FROM program WHERE {' AND '.join(clauses)} ORDER BY created_at DESC", tuple(params))


def list_projects(conn, organization_id: str, program_id: Optional[str] = None, status: Optional[str] = None) -> Sequence[Mapping]:
    clauses = ["organization_id = %s"]
    params: list = [uuid.UUID(organization_id)]
    if program_id:
        clauses.append("program_id = %s")
        params.append(uuid.UUID(program_id))
    if status:
        clauses.append("status = %s")
        params.append(status)
    return model._rows(conn, f"SELECT * FROM project WHERE {' AND '.join(clauses)} ORDER BY created_at DESC", tuple(params))


def _project_transition(conn, project_id: str, to_status: str, actor_type: str, actor_id: Optional[str] = None, note: Optional[str] = None) -> Mapping:
    if to_status not in model.all_states(PROJECT):
        raise ValueError(f"unknown status: {to_status}")
    conn2, own = model._conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM project WHERE id = %s FOR UPDATE", (uuid.UUID(project_id),))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"project not found: {project_id}")
            current = row["status"]
            if to_status == current:
                raise ValueError(f"already in state {to_status}")
            if to_status not in model.allowed_transitions(PROJECT, current):
                raise ValueError(f"cannot transition from {current} to {to_status}")
            if to_status == "on_hold" and not note:
                raise ValueError("on_hold requires a reason note")
            now = datetime.now(timezone.utc)
            started_at = row["started_at"]
            completed_at = row["completed_at"]
            cancelled_at = row["cancelled_at"]
            if to_status == "active" and not started_at:
                started_at = now
            if to_status == "done":
                completed_at = now
            if to_status == "cancelled":
                cancelled_at = now
            cur.execute(
                """
                UPDATE project
                SET status = %s, started_at = %s, completed_at = %s, cancelled_at = %s,
                    version = version + 1, updated_at = now()
                WHERE id = %s RETURNING *
                """,
                (to_status, started_at, completed_at, cancelled_at, uuid.UUID(project_id)),
            )
            updated = cur.fetchone()
            conn2.commit()
            return updated
    finally:
        if own:
            conn2.close()


def start(conn, project_id: str, actor_type: str, actor_id: Optional[str] = None) -> Mapping:
    return _project_transition(conn, project_id, "active", actor_type, actor_id)


def hold(conn, project_id: str, note: str, actor_type: str, actor_id: Optional[str] = None) -> Mapping:
    return _project_transition(conn, project_id, "on_hold", actor_type, actor_id, note)


def resume(conn, project_id: str, actor_type: str, actor_id: Optional[str] = None) -> Mapping:
    return _project_transition(conn, project_id, "active", actor_type, actor_id)


def complete(conn, project_id: str, actor_type: str, actor_id: Optional[str] = None) -> Mapping:
    return _project_transition(conn, project_id, "done", actor_type, actor_id)


def cancel(conn, project_id: str, actor_type: str, actor_id: Optional[str] = None) -> Mapping:
    return _project_transition(conn, project_id, "cancelled", actor_type, actor_id)


def project_rollup(conn, project_id: str) -> Mapping:
    """Aggregate work-item status counts for a project (passive)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT status, COUNT(*) AS count FROM work_item WHERE project_id = %s GROUP BY status",
            (uuid.UUID(project_id),),
        )
        counts = {r["status"]: r["count"] for r in cur.fetchall()}
    proj = get_project(conn, project_id)
    return {
        "project_id": project_id,
        "status": proj["status"] if proj else None,
        "objective_id": str(proj["objective_id"]) if proj and proj["objective_id"] else None,
        "budget_id": str(proj["budget_id"]) if proj and proj["budget_id"] else None,
        "work_item_counts": counts,
    }


def program_rollup(conn, program_id: str) -> Mapping:
    prog = get_program(conn, program_id)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT status, COUNT(*) AS count FROM project WHERE program_id = %s GROUP BY status",
            (uuid.UUID(program_id),),
        )
        counts = {r["status"]: r["count"] for r in cur.fetchall()}
    return {
        "program_id": program_id,
        "objective_id": str(prog["objective_id"]) if prog and prog["objective_id"] else None,
        "budget_id": str(prog["budget_id"]) if prog and prog["budget_id"] else None,
        "project_counts": counts,
    }


def _as_ts(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
