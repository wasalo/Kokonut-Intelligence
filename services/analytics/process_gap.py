"""Process gap analysis and maturity assessment service.

Compares target-state process metrics against as-is actuals,
computes gaps, assigns CMMI-inspired maturity levels, and
recommends improvement initiatives.

Schema: 191_process_targets.sql
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db
from services.analytics import process_mining as pm, value_stream


def _conn():
    return get_db()


def _row_to_dict(row: psycopg2.extras.RealDictRow) -> Dict[str, Any]:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            d[k] = None
    return d


def _compute_actual(
    conn, entity_type: str, metric_name: str, location_id: Optional[str] = None,
) -> Optional[float]:
    """Compute the actual value for a given metric on an entity type."""
    if metric_name == "lead_time_days":
        return _actual_lead_time(conn, entity_type)
    elif metric_name == "fty_pct":
        return _actual_fty(conn, entity_type)
    elif metric_name == "rework_rate_pct":
        return _actual_rework(conn, entity_type)
    elif metric_name == "cycle_time_days":
        return _actual_cycle_time(conn, entity_type)
    elif metric_name == "delivery_success_pct":
        return _actual_delivery_success(conn)
    elif metric_name == "avg_latency_ms":
        return _actual_avg_latency(conn)
    return None


def _actual_lead_time(conn, entity_type: str) -> Optional[float]:
    """Mean draft->goal days for published instances."""
    model = pm.load_model(conn, entity_type)
    goal = pm.goal_state(model)
    if not goal:
        return None
    traces = pm.get_traces(conn, entity_type=entity_type)
    days_list = []
    for (_etype, eid), trace in traces.items():
        if not trace:
            continue
        start = trace[0]["at"]
        end = None
        for t in trace:
            if t["to_status"] == goal:
                end = t["at"]
                break
        if start and end:
            days_list.append((end - start).total_seconds() / 86400.0)
    return round(sum(days_list) / len(days_list), 4) if days_list else None


def _actual_fty(conn, entity_type: str) -> Optional[float]:
    """First-time-through yield percentage."""
    model = pm.load_model(conn, entity_type)
    goal = pm.goal_state(model)
    fail = pm.fail_state(model)
    if not goal:
        return None
    traces = pm.get_traces(conn, entity_type=entity_type)
    total = 0
    passing = 0
    for (_etype, eid), trace in traces.items():
        seq = [t["to_status"] for t in trace]
        if not seq:
            continue
        total += 1
        if fail and fail in seq:
            continue
        if seq[-1] == goal:
            passing += 1
    return round(100.0 * passing / total, 1) if total > 0 else None


def _actual_rework(conn, entity_type: str) -> Optional[float]:
    """Rework rate: percentage of instances that entered a failure state."""
    fail = pm.fail_state(pm.load_model(conn, entity_type))
    if not fail:
        return 0.0
    traces = pm.get_traces(conn, entity_type=entity_type)
    total = 0
    reworked = 0
    for (_etype, eid), trace in traces.items():
        if not trace:
            continue
        total += 1
        seq = [t["to_status"] for t in trace]
        if fail in seq:
            reworked += 1
    return round(100.0 * reworked / total, 1) if total > 0 else None


def _actual_cycle_time(conn, entity_type: str) -> Optional[float]:
    """Mean end-to-end cycle time in days."""
    ct = pm.cycle_time_distribution(conn, entity_type=entity_type)
    if not ct:
        return None
    days = [c["cycle_time_days"] for c in ct if c.get("cycle_time_days")]
    return round(sum(days) / len(days), 4) if days else None


def _actual_delivery_success(conn) -> Optional[float]:
    """Event delivery success percentage from event_handler_log."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'success') AS success,
                    COUNT(*) AS total
                FROM event_handler_log
            """)
            row = cur.fetchone()
            if row and row[1] > 0:
                return round(100.0 * row[0] / row[1], 1)
    except Exception:
        pass
    return None


def _actual_avg_latency(conn) -> Optional[float]:
    """Average event handler execution latency in ms."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT AVG(duration_ms) FROM event_handler_log
                WHERE status = 'success' AND duration_ms IS NOT NULL
            """)
            row = cur.fetchone()
            if row and row[0] is not None:
                return round(float(row[0]), 1)
    except Exception:
        pass
    return None


def _compute_gap(
    target_value: float, actual_value: float, target_direction: str,
) -> Tuple[float, float]:
    """Compute gap_value and gap_pct.

    gap_value = actual - target (positive = over target).
    For 'lte' targets, positive gap means actual exceeds target (bad).
    For 'gte' targets, negative gap means actual is below target (bad).
    """
    gap = actual_value - target_value
    gap_pct = round(100.0 * gap / target_value, 1) if target_value != 0 else None
    return gap, gap_pct


def _assign_maturity(
    gap_pct: Optional[float],
    has_spec: bool,
    has_conformance: bool,
    conformance_ratio: Optional[float],
    has_spc: bool,
    has_targets: bool,
    has_feedback: bool,
) -> Tuple[int, str]:
    """Auto-assign maturity level based on process capabilities."""
    if gap_pct is not None and gap_pct < 10 and has_feedback:
        return 5, "Optimizing"
    if gap_pct is not None and gap_pct < 20 and has_spc and has_targets:
        return 4, "Quantitatively Managed"
    if has_conformance and conformance_ratio is not None and conformance_ratio > 0.8:
        return 3, "Defined"
    if has_spec:
        return 2, "Managed"
    return 1, "Initial"


def assess_process(
    conn,
    process_key: str,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Full gap analysis for a process: loads targets, computes actuals, calculates gaps."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM process_target WHERE process_key = %s ORDER BY metric_name",
        (process_key,),
    )
    targets = [_row_to_dict(r) for r in cur.fetchall()]

    gaps = []
    for target in targets:
        entity_type = target.get("entity_type")
        metric_name = target["metric_name"]
        actual = _compute_actual(conn, entity_type, metric_name, location_id) if entity_type else None
        target_val = target["target_value"]
        direction = target.get("target_direction", "lte")

        gap_val = None
        gap_pct = None
        maturity = None
        notes = None

        if actual is not None and target_val is not None:
            gap_val, gap_pct = _compute_gap(target_val, actual, direction)
            if direction == "lte":
                maturity = 5 if gap_val <= 0 else (4 if gap_val < target_val * 0.2 else 3)
            else:
                maturity = 5 if gap_val >= 0 else (4 if gap_val > -target_val * 0.2 else 3)
            if gap_val > 0 and direction == "lte":
                notes = f"Actual ({actual}) exceeds target ({target_val})"
            elif gap_val < 0 and direction == "gte":
                notes = f"Actual ({actual}) below target ({target_val})"
            else:
                notes = f"On or within target (actual={actual}, target={target_val})"
        else:
            notes = "No actual data available"

        gap_record = {
            "process_key": process_key,
            "entity_type": entity_type,
            "metric_name": metric_name,
            "target_value": target_val,
            "actual_value": actual,
            "gap_value": gap_val,
            "gap_pct": gap_pct,
            "maturity_level": maturity,
            "assessment_notes": notes,
        }
        gaps.append(gap_record)

        # Persist gap analysis
        try:
            cur.execute("""
                INSERT INTO process_gap
                    (process_key, entity_type, metric_name, target_value,
                     actual_value, gap_value, gap_pct, maturity_level, assessment_notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                process_key, entity_type, metric_name, target_val,
                actual, gap_val, gap_pct, maturity, notes,
            ))
        except Exception:
            conn.rollback()

    # Overall maturity
    has_spec = _has_workflow_spec(process_key)
    has_conformance, conf_ratio = _has_conformance(conn, process_key)
    has_spc = _has_spc(conn, process_key)
    has_targets = len(targets) > 0
    has_feedback = _has_feedback(conn)

    avg_maturity = None
    maturity_vals = [g["maturity_level"] for g in gaps if g["maturity_level"] is not None]
    if maturity_vals:
        avg_maturity = round(sum(maturity_vals) / len(maturity_vals))

    overall_level, overall_name = _assign_maturity(
        None if avg_maturity is None else (5 - avg_maturity) * 20,
        has_spec, has_conformance, conf_ratio, has_spc, has_targets, has_feedback,
    )

    try:
        cur.execute("""
            INSERT INTO process_maturity (process_key, maturity_level, level_name, description)
            VALUES (%s, %s, %s, %s)
        """, (process_key, overall_level, overall_name,
              f"Auto-assessed maturity for {process_key}"))
        conn.commit()
    except Exception:
        conn.rollback()

    return {
        "process_key": process_key,
        "targets": targets,
        "gaps": gaps,
        "maturity": {
            "level": overall_level,
            "level_name": overall_name,
            "avg_metric_maturity": avg_maturity,
        },
        "capabilities": {
            "has_workflow_spec": has_spec,
            "has_conformance": has_conformance,
            "conformance_ratio": conf_ratio,
            "has_spc": has_spc,
            "has_targets": has_targets,
            "has_feedback": has_feedback,
        },
    }


def _has_workflow_spec(process_key: str) -> bool:
    """Check if a workflow spec exists for this process's entity types."""
    from services.workflow_specs.registry import list_specs
    spec_ids = {s.id for s in list_specs()}
    entity_map = {
        "farm_operations": "farm_activity",
        "harvest_management": "harvest_event",
        "data_publication": "data_stream_post",
        "impact_verification": "impact_claim",
        "stakeholder_feedback": "stakeholder_feedback",
        "agent_execution": "agent_task",
        "reporting": "report_snapshot",
        "metric_governance": "metric_value",
        "work_management": "work_item",
        "event_delivery": "event_bus_delivery",
        "financial_planning": "budget",
        "performance_management": "objective",
        "portfolio_management": "project",
    }
    return entity_map.get(process_key, "") in spec_ids


def _has_conformance(conn, process_key: str) -> Tuple[bool, Optional[float]]:
    """Check if process mining conformance > 80%."""
    entity_map = {
        "farm_operations": "farm_activity",
        "harvest_management": "harvest_event",
        "data_publication": "data_stream_post",
        "impact_verification": "impact_claim",
        "metric_governance": "metric_value",
        "work_management": "work_item",
    }
    etype = entity_map.get(process_key)
    if not etype:
        return False, None
    try:
        traces = pm.get_traces(conn, entity_type=etype)
        if not traces:
            return False, None
        model = pm.load_model(conn, etype)
        conforming = 0
        total = 0
        for (_e, _id), trace in traces.items():
            seq = [t["to_status"] for t in trace]
            if seq:
                total += 1
                is_conf, _ = pm.classify_conformance(seq, model)
                if is_conf:
                    conforming += 1
        if total > 0:
            ratio = conforming / total
            return ratio > 0.8, ratio
    except Exception:
        pass
    return False, None


def _has_spc(conn, process_key: str) -> bool:
    """Check if SPC (process_kpi_snapshot) exists for this process."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM process_kpi_snapshot LIMIT 1"
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def _has_feedback(conn) -> bool:
    """Check if feedback loop is active."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM action_outcome LIMIT 1"
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def assess_all_processes(
    conn,
    location_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Gap analysis across all processes."""
    cur = conn.cursor()
    cur.execute("SELECT process_key FROM process_map WHERE status = 'active' ORDER BY process_key")
    processes = [r[0] for r in cur.fetchall()]
    return [assess_process(conn, pk, location_id) for pk in processes]


def get_maturity_level(conn, process_key: str) -> Optional[Dict[str, Any]]:
    """Returns current (most recent) maturity assessment."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM process_maturity WHERE process_key = %s ORDER BY assessed_at DESC LIMIT 1",
        (process_key,),
    )
    row = cur.fetchone()
    return _row_to_dict(row) if row else None


def assess_maturity(conn, process_key: str) -> Dict[str, Any]:
    """Auto-assess maturity based on capabilities and gap analysis."""
    has_spec = _has_workflow_spec(process_key)
    has_conformance, conf_ratio = _has_conformance(conn, process_key)
    has_spc = _has_spc(conn, process_key)
    has_feedback = _has_feedback(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM process_target WHERE process_key = %s LIMIT 1",
        (process_key,),
    )
    has_targets = cur.fetchone() is not None

    # Compute average gap if available
    cur.execute(
        "SELECT AVG(ABS(gap_pct)) FROM process_gap WHERE process_key = %s AND gap_pct IS NOT NULL",
        (process_key,),
    )
    row = cur.fetchone()
    avg_gap_pct = float(row[0]) if row and row[0] is not None else None

    level, name = _assign_maturity(
        avg_gap_pct, has_spec, has_conformance, conf_ratio,
        has_spc, has_targets, has_feedback,
    )

    return {
        "process_key": process_key,
        "level": level,
        "level_name": name,
        "capabilities": {
            "has_workflow_spec": has_spec,
            "has_conformance": has_conformance,
            "conformance_ratio": conf_ratio,
            "has_spc": has_spc,
            "has_targets": has_targets,
            "has_feedback": has_feedback,
        },
        "avg_gap_pct": avg_gap_pct,
    }


def process_improvement_initiatives(
    conn,
    process_key: str,
) -> List[Dict[str, Any]]:
    """Returns recommended improvement actions based on gap analysis."""
    maturity = assess_maturity(conn, process_key)
    level = maturity["level"]
    caps = maturity["capabilities"]
    initiatives = []

    if not caps["has_workflow_spec"]:
        initiatives.append({
            "priority": "high",
            "action": "Define workflow specification",
            "description": f"Create a formal workflow spec for {process_key} to enable lifecycle tracking.",
            "target_level": 2,
        })

    if not caps["has_conformance"]:
        initiatives.append({
            "priority": "high",
            "action": "Enable process mining conformance",
            "description": "Instrument lifecycle transitions and achieve >80% conformance.",
            "target_level": 3,
        })
    elif caps["conformance_ratio"] is not None and caps["conformance_ratio"] < 0.9:
        initiatives.append({
            "priority": "medium",
            "action": "Improve conformance rate",
            "description": f"Current conformance is {caps['conformance_ratio']:.0%}. Target >90%.",
            "target_level": 3,
        })

    if not caps["has_spc"]:
        initiatives.append({
            "priority": "medium",
            "action": "Enable statistical process control",
            "description": "Implement SPC control charts for process KPIs.",
            "target_level": 4,
        })

    if not caps["has_targets"]:
        initiatives.append({
            "priority": "medium",
            "action": "Define target-state metrics",
            "description": "Set quantitative targets for lead time, FTY, and cycle time.",
            "target_level": 4,
        })

    if not caps["has_feedback"]:
        initiatives.append({
            "priority": "low",
            "action": "Activate feedback loop",
            "description": "Enable action outcome tracking and threshold auto-tuning.",
            "target_level": 5,
        })

    if level >= 4 and maturity.get("avg_gap_pct") is not None and maturity["avg_gap_pct"] > 20:
        initiatives.append({
            "priority": "high",
            "action": "Close performance gaps",
            "description": f"Average gap is {maturity['avg_gap_pct']:.0f}%. Focus on root cause analysis.",
            "target_level": 5,
        })

    initiatives.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3))
    return initiatives


def process_maturity_trend(
    conn,
    process_key: str,
) -> List[Dict[str, Any]]:
    """Historical maturity assessments for a process."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM process_maturity WHERE process_key = %s ORDER BY assessed_at ASC",
        (process_key,),
    )
    return [_row_to_dict(r) for r in cur.fetchall()]
