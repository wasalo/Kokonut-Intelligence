"""Cross-entity process interface service.

Provides functions for registering handoff declarations, logging
actual handoff events, computing handoff lead times and SLA
compliance, building cross-entity traces, and measuring full
value-chain cycle times.

Schema: 190_process_interfaces.sql
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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
    return d


def register_handoff(
    conn,
    source_type: str,
    target_type: str,
    handoff_type: str,
    correlation_key: Optional[str] = None,
    sla_hours: Optional[float] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Declare a process interface between two entity types."""
    sql = """
        INSERT INTO process_handoff
            (source_entity_type, target_entity_type, handoff_type,
             correlation_key, sla_hours, description)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
            handoff_type = EXCLUDED.handoff_type,
            correlation_key = EXCLUDED.correlation_key,
            sla_hours = EXCLUDED.sla_hours,
            description = EXCLUDED.description
        RETURNING *
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (source_type, target_type, handoff_type,
                          correlation_key, sla_hours, description))
        return _row_to_dict(cur.fetchone())


def record_handoff(
    conn,
    source_type: str,
    source_id,
    target_type: str,
    target_id=None,
    handoff_id=None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Log an actual handoff event with elapsed time computation."""
    handoff_at = datetime.now(timezone.utc)

    elapsed_hours = None
    met_sla = None

    if handoff_id is None:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT id, correlation_key, sla_hours FROM process_handoff "
            "WHERE source_entity_type = %s AND target_entity_type = %s",
            (source_type, target_type),
        )
        row = cur.fetchone()
        if row:
            handoff_id = row["id"]
            sla_hours = row["sla_hours"]
            corr_key = row["correlation_key"]

            if corr_key and sla_hours:
                elapsed_hours = _compute_elapsed(
                    conn, source_type, source_id, handoff_at, corr_key
                )
                if elapsed_hours is not None:
                    met_sla = elapsed_hours <= sla_hours

    sql = """
        INSERT INTO process_handoff_log
            (source_entity_type, source_entity_id, target_entity_type,
             target_entity_id, handoff_id, handoff_at, elapsed_hours,
             met_sla, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (
            source_type, source_id, target_type,
            target_id, handoff_id, handoff_at,
            elapsed_hours, met_sla,
            psycopg2.extras.Json(metadata or {}),
        ))
        return _row_to_dict(cur.fetchone())


def _compute_elapsed(
    conn, source_type: str, source_id, handoff_at: datetime,
    correlation_key: str,
) -> Optional[float]:
    """Compute hours between source entity creation and handoff."""
    table_map = {
        "harvest_event": "harvest_event",
        "data_stream_post": "data_stream_post",
        "impact_claim": "impact_claim",
        "farm_activity": "farm_activity",
        "stakeholder_feedback": "stakeholder_feedback",
        "agent_task": "agent_task",
        "metric_value": "metric_value",
        "report_snapshot": "report_snapshot",
    }
    table = table_map.get(source_type)
    if not table:
        return None

    time_col = "created_at"
    corr_col = correlation_key if correlation_key != "subject_id" else "subject_id"

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {time_col} FROM {table} WHERE id = %s::uuid",
                (str(source_id),),
            )
            row = cur.fetchone()
            if row and row[0]:
                delta = handoff_at - row[0]
                return delta.total_seconds() / 3600.0
    except Exception:
        pass
    return None


def handoff_lead_times(
    conn,
    location_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Average handoff elapsed hours per source->target pair."""
    sql = """
        SELECT
            ph.source_entity_type,
            ph.target_entity_type,
            ph.handoff_type,
            ph.sla_hours,
            COUNT(phl.id) AS total_handoffs,
            ROUND(AVG(phl.elapsed_hours)::numeric, 2) AS avg_elapsed_hours,
            ROUND(MIN(phl.elapsed_hours)::numeric, 2) AS min_elapsed_hours,
            ROUND(MAX(phl.elapsed_hours)::numeric, 2) AS max_elapsed_hours,
            COUNT(phl.id) FILTER (WHERE phl.met_sla = TRUE) AS sla_met_count,
            COUNT(phl.id) FILTER (WHERE phl.met_sla = FALSE) AS sla_breached_count
        FROM process_handoff ph
        LEFT JOIN process_handoff_log phl ON phl.handoff_id = ph.id
        GROUP BY ph.source_entity_type, ph.target_entity_type,
                 ph.handoff_type, ph.sla_hours
        ORDER BY ph.source_entity_type, ph.target_entity_type
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return [_row_to_dict(r) for r in cur.fetchall()]


def handoff_sla_compliance(
    conn,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Percentage of handoffs that met SLA per source->target pair."""
    sql = """
        SELECT
            ph.source_entity_type,
            ph.target_entity_type,
            ph.sla_hours,
            COUNT(phl.id) AS total,
            COUNT(phl.id) FILTER (WHERE phl.met_sla = TRUE) AS met,
            COUNT(phl.id) FILTER (WHERE phl.met_sla = FALSE) AS breached,
            CASE WHEN COUNT(phl.id) > 0
                 THEN ROUND(100.0 * COUNT(phl.id) FILTER (WHERE phl.met_sla = TRUE) / COUNT(phl.id), 1)
                 ELSE NULL
            END AS compliance_pct
        FROM process_handoff ph
        LEFT JOIN process_handoff_log phl ON phl.handoff_id = ph.id
        WHERE ph.sla_hours IS NOT NULL
        GROUP BY ph.source_entity_type, ph.target_entity_type, ph.sla_hours
        ORDER BY compliance_pct ASC NULLS LAST
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        pairs = [_row_to_dict(r) for r in cur.fetchall()]

    total_all = sum(p["total"] for p in pairs)
    met_all = sum(p["met"] for p in pairs)

    return {
        "pairs": pairs,
        "overall": {
            "total": total_all,
            "met": met_all,
            "breached": total_all - met_all,
            "compliance_pct": round(100.0 * met_all / total_all, 1) if total_all > 0 else None,
        },
    }


def build_process_trace(
    conn,
    trace_key: str,
) -> List[Dict[str, Any]]:
    """Reconstruct end-to-end trace across entity types."""
    sql = """
        SELECT * FROM process_trace
        WHERE trace_key = %s
        ORDER BY step_order ASC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (trace_key,))
        return [_row_to_dict(r) for r in cur.fetchall()]


def add_trace_step(
    conn,
    trace_key: str,
    entity_type: str,
    entity_id,
    step_order: int,
    entered_at: Optional[datetime] = None,
    exited_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Add a step to a cross-entity trace."""
    duration_hours = None
    if entered_at and exited_at:
        delta = exited_at - entered_at
        duration_hours = delta.total_seconds() / 3600.0

    sql = """
        INSERT INTO process_trace
            (trace_key, entity_type, entity_id, step_order,
             entered_at, exited_at, duration_hours)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trace_key, entity_type, entity_id) DO UPDATE SET
            step_order = EXCLUDED.step_order,
            entered_at = EXCLUDED.entered_at,
            exited_at = EXCLUDED.exited_at,
            duration_hours = EXCLUDED.duration_hours
        RETURNING *
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (
            trace_key, entity_type, entity_id, step_order,
            entered_at, exited_at, duration_hours,
        ))
        return _row_to_dict(cur.fetchone())


def cross_entity_cycle_times(
    conn,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Full value-chain cycle time (first entity creation -> last entity published).

    Groups traces by trace_key and computes total elapsed time
    from the earliest entered_at to the latest exited_at across
    all entity types in the trace.
    """
    sql = """
        SELECT
            trace_key,
            COUNT(DISTINCT entity_type) AS entity_types,
            COUNT(*) AS total_steps,
            MIN(entered_at) AS chain_start,
            MAX(exited_at) AS chain_end,
            ROUND(SUM(duration_hours)::numeric, 2) AS total_duration_hours,
            ROUND(AVG(duration_hours)::numeric, 2) AS avg_step_duration_hours
        FROM process_trace
        WHERE entered_at IS NOT NULL
        GROUP BY trace_key
        HAVING COUNT(DISTINCT entity_type) > 1
        ORDER BY chain_start DESC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        traces = [_row_to_dict(r) for r in cur.fetchall()]

    for trace in traces:
        if trace.get("chain_start") and trace.get("chain_end"):
            cs = trace["chain_start"]
            ce = trace["chain_end"]
            if isinstance(cs, str):
                cs = datetime.fromisoformat(cs)
            if isinstance(ce, str):
                ce = datetime.fromisoformat(ce)
            trace["wall_clock_hours"] = round(
                (ce - cs).total_seconds() / 3600.0, 2
            )

    return {"traces": traces, "count": len(traces)}
