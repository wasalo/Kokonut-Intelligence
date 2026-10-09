"""Business Architecture Capability Map service layer.

Provides CRUD, hierarchy traversal, maturity aggregation, and
coverage analysis for the business_capability, capability_process_map,
capability_service_map, and capability_maturity_assessment tables
introduced in migration 207_capability_map.sql.
"""

from __future__ import annotations

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


# --- CRUD ----------------------------------------------------------------------

def create_capability(
    name: str,
    *,
    description: str = "",
    capability_type: str = "core",
    parent_id: Optional[str] = None,
    guild_key: Optional[str] = None,
    maturity_level: Optional[int] = None,
    owner_role: Optional[str] = None,
    status: str = "active",
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create a new business capability."""
    cap_id = str(uuid_mod.uuid4())
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO business_capability "
                "(id, name, description, capability_type, parent_id, guild_key, "
                "maturity_level, owner_role, status, metadata) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
                "RETURNING *",
                (cap_id, name, description, capability_type,
                 parent_id, guild_key, maturity_level, owner_role, status,
                 "{}" if metadata is None else __import__("json").dumps(metadata)),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_capability(cap_id: str) -> Optional[Dict[str, Any]]:
    """Get a capability by ID."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM business_capability WHERE id = %s::uuid", (cap_id,)
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def list_capabilities(
    *,
    guild_key: Optional[str] = None,
    capability_type: Optional[str] = None,
    parent_id: Optional[str] = None,
    status: Optional[str] = "active",
) -> List[Dict[str, Any]]:
    """List capabilities with optional filters."""
    clauses: List[str] = []
    params: List[Any] = []
    if guild_key:
        clauses.append("guild_key = %s")
        params.append(guild_key)
    if capability_type:
        clauses.append("capability_type = %s")
        params.append(capability_type)
    if parent_id:
        clauses.append("parent_id = %s::uuid")
        params.append(parent_id)
    elif parent_id is None and guild_key is None:
        clauses.append("parent_id IS NULL")
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM business_capability{where} "
                "ORDER BY guild_key, capability_type, name",
                params,
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def update_capability(cap_id: str, **fields) -> Optional[Dict[str, Any]]:
    """Update a capability. Returns updated row or None."""
    allowed = {
        "name", "description", "capability_type", "parent_id",
        "guild_key", "maturity_level", "owner_role", "status", "metadata",
    }
    sets = []
    params: List[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "metadata":
            import json
            sets.append(f"{k} = %s::jsonb")
            params.append(json.dumps(v))
        else:
            sets.append(f"{k} = %s")
            params.append(v)
    if not sets:
        return None
    params.append(cap_id)
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE business_capability SET {', '.join(sets)} "
                "WHERE id = %s::uuid RETURNING *",
                params,
            )
            conn.commit()
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


# --- Process mapping -----------------------------------------------------------

def map_process(capability_id: str, process_key: str, *, is_primary: bool = True) -> Dict:
    """Link a capability to a process."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO capability_process_map (capability_id, process_key, is_primary) "
                "VALUES (%s::uuid, %s, %s) ON CONFLICT (capability_id, process_key) DO NOTHING",
                (capability_id, process_key, is_primary),
            )
            conn.commit()
            return {"capability_id": capability_id, "process_key": process_key}


def unmap_process(capability_id: str, process_key: str) -> bool:
    """Remove a capability-process link."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM capability_process_map "
                "WHERE capability_id = %s::uuid AND process_key = %s",
                (capability_id, process_key),
            )
            conn.commit()
            return cur.rowcount > 0


def get_capability_processes(capability_id: str) -> List[Dict[str, Any]]:
    """Get all processes linked to a capability."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT cpm.*, pm.name AS process_name, pm.process_type "
                "FROM capability_process_map cpm "
                "JOIN process_map pm ON cpm.process_key = pm.process_key "
                "WHERE cpm.capability_id = %s::uuid "
                "ORDER BY pm.process_type, pm.name",
                (capability_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


# --- Service mapping -----------------------------------------------------------

def map_service(capability_id: str, service_name: str, *, is_primary: bool = True) -> Dict:
    """Link a capability to a service."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO capability_service_map (capability_id, service_name, is_primary) "
                "VALUES (%s::uuid, %s, %s) ON CONFLICT (capability_id, service_name) DO NOTHING",
                (capability_id, service_name, is_primary),
            )
            conn.commit()
            return {"capability_id": capability_id, "service_name": service_name}


def unmap_service(capability_id: str, service_name: str) -> bool:
    """Remove a capability-service link."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM capability_service_map "
                "WHERE capability_id = %s::uuid AND service_name = %s",
                (capability_id, service_name),
            )
            conn.commit()
            return cur.rowcount > 0


def get_capability_services(capability_id: str) -> List[Dict[str, Any]]:
    """Get all services linked to a capability."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT csm.*, sr.category, sr.version, sr.status AS service_status "
                "FROM capability_service_map csm "
                "JOIN service_registry sr ON csm.service_name = sr.name "
                "WHERE csm.capability_id = %s::uuid "
                "ORDER BY sr.category, sr.name",
                (capability_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


# --- Maturity assessment -------------------------------------------------------

def record_maturity(
    capability_id: str,
    maturity_level: int,
    *,
    assessed_by: Optional[str] = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Record a maturity assessment for a capability."""
    ass_id = str(uuid_mod.uuid4())
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO capability_maturity_assessment "
                "(id, capability_id, maturity_level, assessed_by, notes, metadata) "
                "VALUES (%s, %s::uuid, %s, %s, %s, %s::jsonb) "
                "RETURNING *",
                (ass_id, capability_id, maturity_level, assessed_by, notes,
                 "{}" if metadata is None else __import__("json").dumps(metadata)),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def get_maturity_history(capability_id: str) -> List[Dict[str, Any]]:
    """Get maturity assessment history for a capability."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM capability_maturity_assessment "
                "WHERE capability_id = %s::uuid ORDER BY assessed_at DESC",
                (capability_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


# --- Dashboard / analytics -----------------------------------------------------

def get_capability_dashboard(
    *, guild_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get the capability dashboard view with optional guild filter."""
    clauses: List[str] = []
    params: List[Any] = []
    if guild_key:
        clauses.append("guild_key = %s")
        params.append(guild_key)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM v_capability_dashboard{where} "
                "ORDER BY guild_key, capability_type, capability_name",
                params,
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_coverage_analysis() -> Dict[str, Any]:
    """Analyze coverage: capabilities without processes, processes without services."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT bc.id, bc.name, bc.guild_key, "
                "(SELECT COUNT(*) FROM capability_process_map cpm "
                " WHERE cpm.capability_id = bc.id) AS process_count, "
                "(SELECT COUNT(*) FROM capability_service_map csm "
                " WHERE csm.capability_id = bc.id) AS service_count "
                "FROM business_capability bc WHERE bc.status = 'active' "
                "ORDER BY bc.guild_key, bc.name"
            )
            caps = [_row_to_dict(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT pm.process_key, pm.name, pm.process_type, "
                "(SELECT COUNT(*) FROM capability_process_map cpm "
                " WHERE cpm.process_key = pm.process_key) AS capability_count "
                "FROM process_map pm ORDER BY pm.process_type, pm.name"
            )
            procs = [_row_to_dict(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT sr.name, sr.category, "
                "(SELECT COUNT(*) FROM capability_service_map csm "
                " WHERE csm.service_name = sr.name) AS capability_count "
                "FROM service_registry sr ORDER BY sr.category, sr.name"
            )
            svcs = [_row_to_dict(r) for r in cur.fetchall()]

        return {
            "capabilities": caps,
            "unmapped_processes": [p for p in procs if p["capability_count"] == 0],
            "unmapped_services": [s for s in svcs if s["capability_count"] == 0],
            "total_capabilities": len(caps),
            "total_processes": len(procs),
            "total_services": len(svcs),
        }


def get_hierarchy() -> List[Dict[str, Any]]:
    """Get the full capability hierarchy (guild → core)."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM business_capability WHERE status = 'active' "
                "ORDER BY guild_key, capability_type, name"
            )
            all_caps = [_row_to_dict(r) for r in cur.fetchall()]
    by_parent: Dict[Optional[str], List] = {}
    for c in all_caps:
        pid = c.get("parent_id")
        by_parent.setdefault(pid, []).append(c)

    def build_tree(parent_id=None, depth=0):
        children = by_parent.get(parent_id, [])
        result = []
        for c in children:
            c["_depth"] = depth
            c["_children"] = build_tree(c["id"], depth + 1)
            result.append(c)
        return result

    return build_tree()
