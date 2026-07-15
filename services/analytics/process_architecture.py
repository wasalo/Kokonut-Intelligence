"""Process architecture service layer.

Provides CRUD and query functions for the BPM-inspired process map,
process ownership, and entity-type-to-process mappings introduced in
migration 188_process_architecture.sql.
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


# --- Process Map CRUD -------------------------------------------------------

def list_processes(
    *,
    process_type: Optional[str] = None,
    parent_key: Optional[str] = None,
    location_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    status: Optional[str] = "active",
) -> List[Dict[str, Any]]:
    """List process_map rows with optional filters."""
    clauses: List[str] = []
    params: List[Any] = []
    if process_type:
        clauses.append("process_type = %s")
        params.append(process_type)
    if parent_key:
        clauses.append("parent_process_key = %s")
        params.append(parent_key)
    elif parent_key is None and not process_type:
        clauses.append("parent_process_key IS NULL")
    if location_id:
        clauses.append("location_id = %s")
        params.append(location_id)
    if organization_id:
        clauses.append("organization_id = %s")
        params.append(organization_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f"SELECT * FROM process_map WHERE {where} ORDER BY process_key"
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_process(process_key: str) -> Optional[Dict[str, Any]]:
    """Get a single process_map row."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM process_map WHERE process_key = %s", (process_key,))
            r = cur.fetchone()
            return _row_to_dict(r) if r else None


def create_process(
    *,
    process_key: str,
    name: str,
    process_type: str,
    description: Optional[str] = None,
    parent_process_key: Optional[str] = None,
    location_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a new process_map entry."""
    sql = """
        INSERT INTO process_map (process_key, name, description, process_type,
                                 parent_process_key, location_id, organization_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (
                process_key, name, description, process_type,
                parent_process_key, location_id, organization_id,
                json.dumps(metadata or {}),
            ))
            conn.commit()
            return _row_to_dict(cur.fetchone())


def update_process(process_key: str, **fields: Any) -> Optional[Dict[str, Any]]:
    """Update a process_map row."""
    if not fields:
        return get_process(process_key)
    allowed = {"name", "description", "status", "metadata", "location_id", "organization_id"}
    sets = []
    params: List[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "metadata":
            v = json.dumps(v)
        sets.append(f"{k} = %s")
        params.append(v)
    if not sets:
        return get_process(process_key)
    sets.append("updated_at = now()")
    params.append(process_key)
    sql = f"UPDATE process_map SET {', '.join(sets)} WHERE process_key = %s RETURNING *"
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            conn.commit()
            r = cur.fetchone()
            return _row_to_dict(r) if r else None


def delete_process(process_key: str) -> bool:
    """Delete a process_map entry."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM process_map WHERE process_key = %s", (process_key,))
            conn.commit()
            return cur.rowcount > 0


# --- Process Ownership -------------------------------------------------------

def list_ownership(process_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """List process_ownership rows."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if process_key:
                cur.execute(
                    "SELECT * FROM process_ownership WHERE process_key = %s ORDER BY raci_role",
                    (process_key,),
                )
            else:
                cur.execute("SELECT * FROM process_ownership ORDER BY process_key, raci_role")
            return [_row_to_dict(r) for r in cur.fetchall()]


def assign_ownership(
    *,
    process_key: str,
    party_type: str,
    party_id: str,
    raci_role: str,
) -> Dict[str, Any]:
    """Assign RACI role to a party for a process."""
    sql = """
        INSERT INTO process_ownership (process_key, party_type, party_id, raci_role)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (process_key, party_type, party_id, raci_role) DO NOTHING
        RETURNING *
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (process_key, party_type, party_id, raci_role))
            conn.commit()
            r = cur.fetchone()
            return _row_to_dict(r) if r else {"process_key": process_key, "party_type": party_type,
                                                "party_id": party_id, "raci_role": raci_role}


def remove_ownership(process_key: str, party_type: str, party_id: str, raci_role: str) -> bool:
    """Remove a specific RACI assignment."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM process_ownership WHERE process_key=%s AND party_type=%s AND party_id=%s AND raci_role=%s",
                (process_key, party_type, party_id, raci_role),
            )
            conn.commit()
            return cur.rowcount > 0


# --- Entity Mapping ---------------------------------------------------------

def list_entity_mappings(process_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """List process_entity_mapping rows."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if process_key:
                cur.execute(
                    "SELECT * FROM process_entity_mapping WHERE process_key = %s ORDER BY entity_type",
                    (process_key,),
                )
            else:
                cur.execute("SELECT * FROM process_entity_mapping ORDER BY process_key, entity_type")
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_entity_mapping(entity_type: str) -> Optional[Dict[str, Any]]:
    """Get the process mapping for a specific entity type."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM process_entity_mapping WHERE entity_type = %s",
                (entity_type,),
            )
            r = cur.fetchone()
            return _row_to_dict(r) if r else None


def create_entity_mapping(
    *,
    process_key: str,
    entity_type: str,
    workflow_spec_id: Optional[str] = None,
    lifecycle_model: str = "5-state",
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an entity-type-to-process mapping."""
    sql = """
        INSERT INTO process_entity_mapping (process_key, entity_type, workflow_spec_id,
                                            lifecycle_model, description)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (entity_type) DO UPDATE SET
            process_key = EXCLUDED.process_key,
            workflow_spec_id = EXCLUDED.workflow_spec_id,
            lifecycle_model = EXCLUDED.lifecycle_model,
            description = EXCLUDED.description
        RETURNING *
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (process_key, entity_type, workflow_spec_id, lifecycle_model, description))
            conn.commit()
            return _row_to_dict(cur.fetchone())


def delete_entity_mapping(entity_type: str) -> bool:
    """Delete an entity mapping."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM process_entity_mapping WHERE entity_type = %s", (entity_type,))
            conn.commit()
            return cur.rowcount > 0


# --- Process Hierarchy -------------------------------------------------------

def get_process_hierarchy() -> List[Dict[str, Any]]:
    """Return the process map as a hierarchical tree."""
    all_procs = list_processes(parent_key=None)
    children = {}
    for proc in list_processes(parent_key="__ALL__"):
        pk = proc.get("parent_process_key")
        if pk:
            children.setdefault(pk, []).append(proc)
    for proc in list_processes():
        pk = proc.get("parent_process_key")
        if pk:
            children.setdefault(pk, []).append(proc)
    for proc in all_procs:
        proc["children"] = children.get(proc["process_key"], [])
    return all_procs


def get_process_with_children(process_key: str) -> Optional[Dict[str, Any]]:
    """Return a single process and its direct children."""
    proc = get_process(process_key)
    if not proc:
        return None
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM process_map WHERE parent_process_key = %s ORDER BY process_key",
                (process_key,),
            )
            proc["children"] = [_row_to_dict(r) for r in cur.fetchall()]
    return proc
