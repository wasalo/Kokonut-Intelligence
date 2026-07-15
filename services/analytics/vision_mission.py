"""Vision, Mission & Values service layer.

Provides CRUD and approval workflow for the vision_mission table
introduced in migration 209_vision_mission.sql.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.db import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD


def _conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )


def _row_to_dict(row: psycopg2.extras.RealDictRow) -> Dict[str, Any]:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, uuid_mod.UUID):
            d[k] = str(v)
    return d


def create_statement(
    statement_text: str,
    *,
    statement_type: str,
    entity_type: str = "platform",
    entity_id: Optional[str] = None,
    effective_date: Optional[str] = None,
    review_date: Optional[str] = None,
    status: str = "draft",
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create a vision/mission/values statement."""
    stmt_id = str(uuid_mod.uuid4())
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO vision_mission "
                "(id, entity_type, entity_id, statement_type, statement_text, "
                "effective_date, review_date, status, metadata) "
                "VALUES (%s, %s, %s, %s, %s, COALESCE(%s::date, CURRENT_DATE), %s, %s, %s::jsonb) "
                "RETURNING *",
                (stmt_id, entity_type, entity_id, statement_type, statement_text,
                 effective_date, review_date, status,
                 "{}" if metadata is None else json.dumps(metadata)),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_statement(stmt_id: str) -> Optional[Dict[str, Any]]:
    """Get a statement by ID."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM vision_mission WHERE id = %s::uuid", (stmt_id,)
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def list_statements(
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    statement_type: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List statements with optional filters."""
    clauses: List[str] = []
    params: List[Any] = []
    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    if entity_id:
        clauses.append("entity_id = %s::uuid")
        params.append(entity_id)
    if statement_type:
        clauses.append("statement_type = %s")
        params.append(statement_type)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM vision_mission{where} "
                "ORDER BY statement_type, created_at DESC",
                params,
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def approve_statement(
    stmt_id: str,
    *,
    approved_by: str,
) -> Optional[Dict[str, Any]]:
    """Approve a vision/mission/values statement."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE vision_mission SET status = 'approved', "
                "approved_by = %s, approved_at = NOW() "
                "WHERE id = %s::uuid AND status = 'draft' "
                "RETURNING *",
                (approved_by, stmt_id),
            )
            conn.commit()
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def archive_statement(stmt_id: str) -> Optional[Dict[str, Any]]:
    """Archive a statement."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE vision_mission SET status = 'archived' "
                "WHERE id = %s::uuid RETURNING *",
                (stmt_id,),
            )
            conn.commit()
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def get_current_statements(
    *,
    entity_type: str = "platform",
    entity_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get currently approved vision/mission/values."""
    clauses = ["entity_type = %s", "status = 'approved'"]
    params: List[Any] = [entity_type]
    if entity_id:
        clauses.append("entity_id = %s::uuid")
        params.append(entity_id)
    else:
        clauses.append("entity_id IS NULL")
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            where = " AND ".join(clauses)
            cur.execute(
                f"SELECT * FROM vision_mission WHERE {where} "
                "ORDER BY statement_type",
                params,
            )
            return [_row_to_dict(r) for r in cur.fetchall()]
