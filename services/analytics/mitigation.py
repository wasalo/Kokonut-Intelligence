"""Mitigation approach management."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.mitigation")


def create_mitigation(
    conn,
    location_id: str,
    approach_key: str,
    approach_name: str,
    mitigation_type: str,
    description: str,
    source_table: str = None,
    source_id: str = None,
    mechanism: str = None,
    target_reduction_pct: float = None,
    target_date: str = None,
    estimated_cost_usd: float = None,
    responsible_party: str = None,
    **kwargs,
) -> str:
    """Create a new mitigation approach."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO mitigation_approach (
            location_id, approach_key, approach_name, mitigation_type,
            source_table, source_id, description, mechanism,
            target_reduction_pct, target_date, estimated_cost_usd,
            responsible_party, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
        ON CONFLICT (location_id, approach_key) DO UPDATE SET
            description = EXCLUDED.description, mechanism = EXCLUDED.mechanism,
            updated_at = NOW()
        RETURNING id
    """, (
        location_id, approach_key, approach_name, mitigation_type,
        source_table, source_id, description, mechanism,
        target_reduction_pct, target_date, estimated_cost_usd,
        responsible_party,
    ))
    mitigation_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Created mitigation approach: %s (type=%s)", approach_key, mitigation_type)
    return mitigation_id


def track_mitigation_outcome(
    conn,
    mitigation_id: str,
    measured_value: float,
    actual_cost_usd: float = None,
    effectiveness_rating: str = None,
) -> Dict[str, Any]:
    """Record actual outcomes for a mitigation approach."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE mitigation_approach SET
            measured_value = %s, measured_date = CURRENT_DATE,
            actual_cost_usd = COALESCE(%s, actual_cost_usd),
            effectiveness_rating = COALESCE(%s, effectiveness_rating),
            updated_at = NOW()
        WHERE id = %s
        RETURNING id, target_reduction_pct, measured_value, target_value
    """, (measured_value, actual_cost_usd, effectiveness_rating, mitigation_id))
    row = cur.fetchone()
    conn.commit()
    cur.close()

    if not row:
        return {"status": "error", "message": "Mitigation not found"}

    target = float(row[1] or 0)
    actual = float(row[2] or 0) if row[2] else None
    target_val = float(row[3] or 0)

    return {
        "mitigation_id": mitigation_id,
        "measured_value": actual,
        "target_reduction_pct": target,
        "target_value": target_val,
    }


def compute_effectiveness(conn, mitigation_id: str) -> Dict[str, Any]:
    """Compare target vs actual effectiveness."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM mitigation_approach WHERE id = %s", (mitigation_id,))
    ma = cur.fetchone()
    cur.close()

    if not ma:
        return {"status": "error", "message": "Mitigation not found"}

    ma = dict(ma)
    baseline = float(ma.get("baseline_value", 0) or 0)
    target = float(ma.get("target_value", 0) or 0)
    measured = float(ma.get("measured_value", 0) or 0)
    target_reduction = float(ma.get("target_reduction_pct", 0) or 0)

    if baseline > 0:
        actual_reduction = ((baseline - measured) / baseline * 100) if measured < baseline else 0
    else:
        actual_reduction = 0

    effectiveness = actual_reduction / target_reduction if target_reduction > 0 else 0

    return {
        "mitigation_id": mitigation_id,
        "baseline": baseline,
        "target_value": target,
        "measured_value": measured,
        "target_reduction_pct": target_reduction,
        "actual_reduction_pct": round(actual_reduction, 2),
        "effectiveness_ratio": round(effectiveness, 4),
        "on_track": effectiveness >= 0.8,
    }


def get_mitigations_by_source(conn, source_table: str, source_id: str) -> List[Dict[str, Any]]:
    """Find all mitigation approaches linked to a source record."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM mitigation_approach
        WHERE source_table = %s AND source_id = %s
        ORDER BY created_at DESC
    """, (source_table, source_id))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def get_mitigations_by_type(conn, mitigation_type: str, location_id: str = None) -> List[Dict[str, Any]]:
    """Filter mitigation approaches by type."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = "SELECT * FROM mitigation_approach WHERE mitigation_type = %s"
    params = [mitigation_type]
    if location_id:
        query += " AND location_id = %s"
        params.append(location_id)
    query += " ORDER BY created_at DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows
