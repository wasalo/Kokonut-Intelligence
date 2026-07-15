"""Strategy Map (Balanced Scorecard) service layer.

Provides CRUD and execution tracking for the strategy_map and
strategy_initiative tables introduced in migration 208_strategy_map.sql.
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


# --- Strategy Map CRUD ---------------------------------------------------------

def create_strategy_entry(
    statement: str,
    *,
    perspective: str,
    entity_type: str = "location",
    entity_id: Optional[str] = None,
    objective_id: Optional[str] = None,
    strategic_theme: Optional[str] = None,
    target_value: Optional[float] = None,
    current_value: Optional[float] = None,
    unit: Optional[str] = None,
    weight: float = 1.0,
    status: str = "on_track",
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create a strategy map entry."""
    entry_id = str(uuid_mod.uuid4())
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO strategy_map "
                "(id, entity_type, entity_id, perspective, objective_id, "
                "strategic_theme, statement, target_value, current_value, "
                "unit, weight, status, metadata) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
                "RETURNING *",
                (entry_id, entity_type, entity_id, perspective, objective_id,
                 strategic_theme, statement, target_value, current_value,
                 unit, weight, status, "{}" if metadata is None else json.dumps(metadata)),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_strategy_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    """Get a strategy map entry by ID."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM strategy_map WHERE id = %s::uuid", (entry_id,)
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def list_strategy_entries(
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    perspective: Optional[str] = None,
    strategic_theme: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List strategy map entries with optional filters."""
    clauses: List[str] = []
    params: List[Any] = []
    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    if entity_id:
        clauses.append("entity_id = %s::uuid")
        params.append(entity_id)
    if perspective:
        clauses.append("perspective = %s")
        params.append(perspective)
    if strategic_theme:
        clauses.append("strategic_theme = %s")
        params.append(strategic_theme)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM strategy_map{where} "
                "ORDER BY perspective, strategic_theme, statement",
                params,
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def update_strategy_entry(entry_id: str, **fields) -> Optional[Dict[str, Any]]:
    """Update a strategy map entry."""
    allowed = {
        "perspective", "objective_id", "strategic_theme", "statement",
        "target_value", "current_value", "unit", "weight", "status", "metadata",
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
    params.append(entry_id)
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE strategy_map SET {', '.join(sets)} "
                "WHERE id = %s::uuid RETURNING *",
                params,
            )
            conn.commit()
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def map_capability(
    strategy_map_id: str,
    capability_id: str,
    *,
    contribution_type: str = "primary",
    expected_impact: Optional[str] = None,
) -> Dict[str, Any]:
    """Link a strategic objective to an enabling business capability."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO strategy_capability_map "
                "(strategy_map_id, capability_id, contribution_type, expected_impact) "
                "VALUES (%s::uuid, %s::uuid, %s, %s) "
                "ON CONFLICT (strategy_map_id, capability_id) DO UPDATE SET "
                "contribution_type = EXCLUDED.contribution_type, "
                "expected_impact = EXCLUDED.expected_impact RETURNING *",
                (strategy_map_id, capability_id, contribution_type, expected_impact),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_strategy_capabilities(strategy_map_id: str) -> List[Dict[str, Any]]:
    """List capabilities required by a strategic objective."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT scm.*, bc.name AS capability_name, bc.guild_key, "
                "bc.maturity_level FROM strategy_capability_map scm "
                "JOIN business_capability bc ON bc.id = scm.capability_id "
                "WHERE scm.strategy_map_id = %s::uuid "
                "ORDER BY scm.contribution_type, bc.name",
                (strategy_map_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


# --- Initiative CRUD -----------------------------------------------------------

def create_initiative(
    strategy_map_id: str,
    name: str,
    *,
    description: str = "",
    work_item_id: Optional[str] = None,
    owner: Optional[str] = None,
    start_date: Optional[str] = None,
    target_date: Optional[str] = None,
    status: str = "planned",
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create a strategy initiative."""
    init_id = str(uuid_mod.uuid4())
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO strategy_initiative "
                "(id, strategy_map_id, name, description, work_item_id, "
                "owner, start_date, target_date, status, metadata) "
                "VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
                "RETURNING *",
                (init_id, strategy_map_id, name, description, work_item_id,
                 owner, start_date, target_date, status,
                 "{}" if metadata is None else json.dumps(metadata)),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_initiative(init_id: str) -> Optional[Dict[str, Any]]:
    """Get an initiative by ID."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM strategy_initiative WHERE id = %s::uuid", (init_id,)
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def list_initiatives(
    *,
    strategy_map_id: Optional[str] = None,
    owner: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List initiatives with optional filters."""
    clauses: List[str] = []
    params: List[Any] = []
    if strategy_map_id:
        clauses.append("strategy_map_id = %s::uuid")
        params.append(strategy_map_id)
    if owner:
        clauses.append("owner = %s")
        params.append(owner)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM strategy_initiative{where} ORDER BY name",
                params,
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def update_initiative(init_id: str, **fields) -> Optional[Dict[str, Any]]:
    """Update an initiative."""
    allowed = {
        "name", "description", "work_item_id", "owner",
        "start_date", "target_date", "completion_pct", "status", "metadata",
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
    params.append(init_id)
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE strategy_initiative SET {', '.join(sets)} "
                "WHERE id = %s::uuid RETURNING *",
                params,
            )
            conn.commit()
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


# --- Execution tracking --------------------------------------------------------

def get_execution_dashboard(
    *, entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get the strategy execution dashboard."""
    clauses: List[str] = []
    params: List[Any] = []
    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    if entity_id:
        clauses.append("entity_id = %s::uuid")
        params.append(entity_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM v_strategy_execution{where} "
                "ORDER BY perspective, objective_statement",
                params,
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_perspective_summary() -> List[Dict[str, Any]]:
    """Get summary statistics by BSC perspective."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT perspective, "
                "COUNT(*) AS entry_count, "
                "COUNT(*) FILTER (WHERE status = 'achieved') AS achieved_count, "
                "COUNT(*) FILTER (WHERE status = 'on_track') AS on_track_count, "
                "COUNT(*) FILTER (WHERE status = 'at_risk') AS at_risk_count, "
                "COUNT(*) FILTER (WHERE status = 'behind') AS behind_count, "
                "ROUND(AVG(CASE WHEN target_value > 0 "
                "  THEN (COALESCE(current_value, 0) / target_value * 100) "
                "  ELSE NULL END), 1) AS avg_progress_pct "
                "FROM strategy_map "
                "GROUP BY perspective "
                "ORDER BY perspective"
            )
            return [_row_to_dict(r) for r in cur.fetchall()]
