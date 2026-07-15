"""BRM Service Component Reference Model (SCRM) service layer.

Provides CRUD and query functions for the service_registry table
introduced in migration 195_service_catalog.sql.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from collections import defaultdict
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


# --- List / Get ---------------------------------------------------------------

def list_services(
    *,
    category: Optional[str] = None,
    status: Optional[str] = "active",
) -> List[Dict[str, Any]]:
    """List service_registry rows with optional category and status filters."""
    clauses: List[str] = []
    params: List[Any] = []
    if category:
        clauses.append("category = %s")
        params.append(category)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f"SELECT * FROM service_registry WHERE {where} ORDER BY category, name"
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def get_service(name: str) -> Optional[Dict[str, Any]]:
    """Get a single service by name."""
    sql = "SELECT * FROM service_registry WHERE name = %s"
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (name,))
                r = cur.fetchone()
                return _row_to_dict(r) if r else None
    except Exception:
        return None


# --- Register / Update --------------------------------------------------------

def register_service(
    *,
    name: str,
    version: str = "1.0.0",
    category: str,
    description: Optional[str] = None,
    health_endpoint: Optional[str] = None,
    owner: Optional[str] = None,
    sla_target_ms: Optional[int] = None,
    dependencies: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Register or update a service (INSERT ON CONFLICT DO UPDATE)."""
    sql = """
        INSERT INTO service_registry
            (name, version, category, description, health_endpoint,
             owner, sla_target_ms, dependencies, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET
            version = EXCLUDED.version,
            category = EXCLUDED.category,
            description = EXCLUDED.description,
            health_endpoint = EXCLUDED.health_endpoint,
            owner = EXCLUDED.owner,
            sla_target_ms = EXCLUDED.sla_target_ms,
            dependencies = EXCLUDED.dependencies,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING *
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (
                    name, version, category, description, health_endpoint,
                    owner, sla_target_ms,
                    json.dumps(dependencies or []),
                    json.dumps(metadata or {}),
                ))
                conn.commit()
                return _row_to_dict(cur.fetchone())
    except Exception:
        return {}


def update_service(name: str, **fields: Any) -> Optional[Dict[str, Any]]:
    """Update a service_registry row.

    Allowed fields: version, description, health_endpoint, owner,
    sla_target_ms, dependencies, metadata, status.
    """
    if not fields:
        return get_service(name)
    allowed = {
        "version", "description", "health_endpoint", "owner",
        "sla_target_ms", "dependencies", "metadata", "status",
    }
    sets: List[str] = []
    params: List[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("dependencies", "metadata"):
            v = json.dumps(v)
        sets.append(f"{k} = %s")
        params.append(v)
    if not sets:
        return get_service(name)
    sets.append("updated_at = NOW()")
    params.append(name)
    sql = f"UPDATE service_registry SET {', '.join(sets)} WHERE name = %s RETURNING *"
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                conn.commit()
                r = cur.fetchone()
                return _row_to_dict(r) if r else None
    except Exception:
        return None


# --- Lifecycle ----------------------------------------------------------------

def deprecate_service(name: str) -> Optional[Dict[str, Any]]:
    """Set status to 'deprecated'."""
    return update_service(name, status="deprecated")


def retire_service(name: str) -> Optional[Dict[str, Any]]:
    """Set status to 'retired'."""
    return update_service(name, status="retired")


# --- Aggregations -------------------------------------------------------------

def services_by_category() -> Dict[str, List[Dict[str, Any]]]:
    """Group services by category."""
    sql = """
        SELECT * FROM service_registry
        WHERE status = 'active'
        ORDER BY category, name
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
                for r in rows:
                    d = _row_to_dict(r)
                    groups[d["category"]].append(d)
                return dict(groups)
    except Exception:
        return {}


def service_health_summary() -> Dict[str, Any]:
    """Return summary: total services, status counts, by-category, avg SLA."""
    sql = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'active') AS active_count,
            COUNT(*) FILTER (WHERE status = 'deprecated') AS deprecated_count,
            COUNT(*) FILTER (WHERE status = 'retired') AS retired_count,
            ROUND(AVG(sla_target_ms) FILTER (WHERE sla_target_ms IS NOT NULL), 0) AS avg_sla_ms
        FROM service_registry
    """
    sql_by_cat = """
        SELECT category, COUNT(*) AS count
        FROM service_registry
        WHERE status = 'active'
        GROUP BY category
        ORDER BY category
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                summary = _row_to_dict(cur.fetchone())
                cur.execute(sql_by_cat)
                by_category = {r["category"]: r["count"] for r in cur.fetchall()}
                summary["by_category"] = by_category
                return summary
    except Exception:
        return {
            "total": 0,
            "active_count": 0,
            "deprecated_count": 0,
            "retired_count": 0,
            "avg_sla_ms": None,
            "by_category": {},
        }
