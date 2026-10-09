"""Value Stream Definitions service layer.

Provides CRUD, stage management, observation recording, and
performance calculation for the value_stream_definition,
value_stream_stage, and value_stream_stage_observation tables
introduced in migration 210_value_stream_definitions.sql.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db


def _conn():
    return get_db()


def _row_to_dict(row: psycopg2.extras.RealDictRow) -> Dict[str, Any]:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, uuid_mod.UUID):
            d[k] = str(v)
    return d


# --- Value Stream Definition CRUD ----------------------------------------------

def create_stream(
    name: str,
    *,
    description: str = "",
    stakeholder_type: Optional[str] = None,
    trigger_event: Optional[str] = None,
    end_state: Optional[str] = None,
    owner_role: Optional[str] = None,
    status: str = "active",
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create a value stream definition."""
    stream_id = str(uuid_mod.uuid4())
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO value_stream_definition "
                "(id, name, description, stakeholder_type, trigger_event, "
                "end_state, owner_role, status, metadata) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
                "RETURNING *",
                (stream_id, name, description, stakeholder_type,
                 trigger_event, end_state, owner_role, status,
                 "{}" if metadata is None else json.dumps(metadata)),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_stream(stream_id: str) -> Optional[Dict[str, Any]]:
    """Get a value stream definition by ID."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM value_stream_definition WHERE id = %s::uuid",
                (stream_id,),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def list_streams(
    *,
    stakeholder_type: Optional[str] = None,
    status: Optional[str] = "active",
) -> List[Dict[str, Any]]:
    """List value stream definitions with optional filters."""
    clauses: List[str] = []
    params: List[Any] = []
    if stakeholder_type:
        clauses.append("stakeholder_type = %s")
        params.append(stakeholder_type)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM value_stream_definition{where} ORDER BY name",
                params,
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def update_stream(stream_id: str, **fields) -> Optional[Dict[str, Any]]:
    """Update a value stream definition."""
    allowed = {
        "name", "description", "stakeholder_type", "trigger_event",
        "end_state", "owner_role", "status", "metadata",
    }
    sets = []
    params: List[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "metadata":
            sets.append(f"{k} = %s::jsonb")
            params.append(json.dumps(v))
        else:
            sets.append(f"{k} = %s")
            params.append(v)
    if not sets:
        return None
    params.append(stream_id)
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE value_stream_definition SET {', '.join(sets)} "
                "WHERE id = %s::uuid RETURNING *",
                params,
            )
            conn.commit()
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


# --- Stage CRUD ----------------------------------------------------------------

def create_stage(
    stream_id: str,
    name: str,
    *,
    description: str = "",
    sequence_order: int = 1,
    process_key: Optional[str] = None,
    target_lead_time_hours: Optional[float] = None,
    target_fty_pct: Optional[float] = None,
    status: str = "active",
) -> Dict[str, Any]:
    """Create a value stream stage."""
    stage_id = str(uuid_mod.uuid4())
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO value_stream_stage "
                "(id, stream_id, name, description, sequence_order, "
                "process_key, target_lead_time_hours, target_fty_pct, status) "
                "VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING *",
                (stage_id, stream_id, name, description, sequence_order,
                 process_key, target_lead_time_hours, target_fty_pct, status),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_stage(stage_id: str) -> Optional[Dict[str, Any]]:
    """Get a stage by ID."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM value_stream_stage WHERE id = %s::uuid",
                (stage_id,),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def list_stages(stream_id: str) -> List[Dict[str, Any]]:
    """List stages for a value stream, ordered by sequence."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT vss.*, pm.name AS process_name "
                "FROM value_stream_stage vss "
                "LEFT JOIN process_map pm ON vss.process_key = pm.process_key "
                "WHERE vss.stream_id = %s::uuid "
                "ORDER BY vss.sequence_order",
                (stream_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def update_stage(stage_id: str, **fields) -> Optional[Dict[str, Any]]:
    """Update a value stream stage."""
    allowed = {
        "name", "description", "sequence_order", "process_key",
        "target_lead_time_hours", "target_fty_pct", "status",
    }
    sets = []
    params: List[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = %s")
        params.append(v)
    if not sets:
        return None
    params.append(stage_id)
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE value_stream_stage SET {', '.join(sets)} "
                "WHERE id = %s::uuid RETURNING *",
                params,
            )
            conn.commit()
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


# --- Observation recording -----------------------------------------------------

def record_observation(
    stage_id: str,
    entity_type: str,
    entity_id: str,
    *,
    actual_lead_time_hours: Optional[float] = None,
    actual_fty_pct: Optional[float] = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Record a performance observation for a stage."""
    obs_id = str(uuid_mod.uuid4())
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO value_stream_stage_observation "
                "(id, stage_id, entity_type, entity_id, "
                "actual_lead_time_hours, actual_fty_pct, notes, metadata) "
                "VALUES (%s, %s::uuid, %s, %s::uuid, %s, %s, %s, %s::jsonb) "
                "RETURNING *",
                (obs_id, stage_id, entity_type, entity_id,
                 actual_lead_time_hours, actual_fty_pct, notes,
                 "{}" if metadata is None else json.dumps(metadata)),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_observations(
    stage_id: str,
    *,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get observations for a stage."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM value_stream_stage_observation "
                "WHERE stage_id = %s::uuid "
                "ORDER BY observed_at DESC LIMIT %s",
                (stage_id, limit),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


# --- Performance views ---------------------------------------------------------

def get_stream_performance(stream_id: str) -> List[Dict[str, Any]]:
    """Get stage-level performance for a value stream."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM v_value_stream_performance "
                "WHERE stream_id = %s::uuid "
                "ORDER BY sequence_order",
                (stream_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_stream_summary() -> List[Dict[str, Any]]:
    """Get stream-level summary for all active value streams."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM v_value_stream_summary ORDER BY stream_name"
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_stream_with_stages(stream_id: str) -> Optional[Dict[str, Any]]:
    """Get a stream with its stages nested."""
    stream = get_stream(stream_id)
    if not stream:
        return None
    stream["stages"] = list_stages(stream_id)
    return stream
