"""Process costing and benchmarking service.

Attributes costs to process steps, benchmarks across locations,
calculates process ROI, and tracks Kaizen improvement initiatives.

Schema: 192_process_costing.sql
"""

from __future__ import annotations

import math
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db


def _conn():
    return get_db()


def _row_to_dict(row: psycopg2.extras.RealDictRow) -> Dict[str, Any]:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            d[k] = None
    return d


def record_process_cost(
    conn,
    entity_type: str,
    entity_id,
    process_key: Optional[str],
    cost_type: str,
    cost_amount: float,
    currency: str = "USD",
    source_event_id=None,
) -> Dict[str, Any]:
    """Record an actual cost observation for an entity instance."""
    sql = """
        INSERT INTO process_cost_observation
            (entity_type, entity_id, process_key, cost_type,
             cost_amount, currency, source_event_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (
            entity_type, entity_id, process_key, cost_type,
            cost_amount, currency, source_event_id,
        ))
        return _row_to_dict(cur.fetchone())


def process_cost_per_instance(
    conn,
    process_key: str,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Average cost per process instance, broken down by cost type."""
    sql = """
        SELECT
            pco.cost_type,
            COUNT(*) AS instance_count,
            ROUND(AVG(pco.cost_amount)::numeric, 4) AS avg_cost,
            ROUND(SUM(pco.cost_amount)::numeric, 4) AS total_cost,
            ROUND(MIN(pco.cost_amount)::numeric, 4) AS min_cost,
            ROUND(MAX(pco.cost_amount)::numeric, 4) AS max_cost
        FROM process_cost_observation pco
        WHERE pco.process_key = %s
    """
    params: List[Any] = [process_key]
    sql += " GROUP BY pco.cost_type ORDER BY pco.cost_type"

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        by_type = [_row_to_dict(r) for r in cur.fetchall()]

    total_instances = max((r["instance_count"] for r in by_type), default=0)
    total_all = sum(r["total_cost"] for r in by_type)
    avg_all = round(total_all / total_instances, 4) if total_instances > 0 else 0

    return {
        "process_key": process_key,
        "total_instances": total_instances,
        "avg_cost_per_instance": avg_all,
        "total_cost": round(total_all, 4),
        "by_cost_type": by_type,
    }


def total_process_cost(
    conn,
    process_key: str,
    location_id: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Total cost for a process over a period."""
    sql = """
        SELECT
            COUNT(*) AS observation_count,
            COUNT(DISTINCT entity_id) AS unique_entities,
            ROUND(SUM(cost_amount)::numeric, 4) AS total_cost,
            ROUND(AVG(cost_amount)::numeric, 4) AS avg_cost,
            currency
        FROM process_cost_observation
        WHERE process_key = %s
    """
    params: List[Any] = [process_key]
    if period_start:
        sql += " AND recorded_at >= %s"
        params.append(period_start)
    if period_end:
        sql += " AND recorded_at <= %s"
        params.append(period_end)
    sql += " GROUP BY currency"

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        currencies = [_row_to_dict(r) for r in cur.fetchall()]

    return {
        "process_key": process_key,
        "period_start": period_start,
        "period_end": period_end,
        "by_currency": currencies,
    }


def process_cost_of_quality(
    conn,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Cost of conformance vs cost of non-conformance.

    Conformance costs: verification, review, inspection.
    Non-conformance costs: rework, rejection, re-processing.
    """
    sql_conf = """
        SELECT COALESCE(SUM(cost_amount), 0) AS total
        FROM process_cost_observation pco
        WHERE pco.cost_type IN ('labor')
          AND pco.process_key IN (
              'metric_governance', 'impact_verification', 'harvest_management'
          )
    """
    sql_nonconf = """
        SELECT COALESCE(SUM(pc.cost_per_instance * sub.instance_count), 0) AS total
        FROM process_cost pc
        JOIN (
            SELECT process_key, COUNT(*) AS instance_count
            FROM process_cost_observation
            WHERE cost_type = 'labor'
            GROUP BY process_key
        ) sub ON pc.process_key = sub.process_key
        WHERE pc.cost_category IN ('rework', 'quality_check', 'editorial_review')
    """

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql_conf)
        conf = float(cur.fetchone()["total"])
        cur.execute(sql_nonconf)
        nonconf = float(cur.fetchone()["total"])

    total = conf + nonconf
    return {
        "cost_of_conformance": round(conf, 4),
        "cost_of_non_conformance": round(nonconf, 4),
        "total_cost_of_quality": round(total, 4),
        "conformance_pct": round(100.0 * conf / total, 1) if total > 0 else None,
        "non_conformance_pct": round(100.0 * nonconf / total, 1) if total > 0 else None,
    }


def benchmark_processes(
    conn,
    location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Compute benchmarks for all process metrics at a location."""
    from services.analytics import process_mining as pm, value_stream

    benchmarks = []
    for etype, _col in value_stream._PIPELINE:
        traces = pm.get_traces(conn, entity_type=etype)
        if not traces:
            continue

        model = pm.load_model(conn, etype)
        goal = pm.goal_state(model)
        fail = pm.fail_state(model)

        total = len(traces)
        conforming = 0
        cycle_times = []
        for (_e, _id), trace in traces.items():
            seq = [t["to_status"] for t in trace]
            if seq:
                is_conf, _ = pm.classify_conformance(seq, model)
                if is_conf:
                    conforming += 1
            if goal and seq and seq[-1] == goal:
                start = trace[0]["at"]
                end = None
                for t in trace:
                    if t["to_status"] == goal:
                        end = t["at"]
                        break
                if start and end:
                    cycle_times.append((end - start).total_seconds() / 86400.0)

        conformance_ratio = round(conforming / total, 4) if total > 0 else None
        avg_cycle = round(sum(cycle_times) / len(cycle_times), 4) if cycle_times else None

        benchmarks.append({
            "entity_type": etype,
            "location_id": location_id,
            "total_instances": total,
            "conformance_ratio": conformance_ratio,
            "avg_cycle_time_days": avg_cycle,
            "sample_size": total,
        })

    return benchmarks


def compare_benchmarks(
    conn,
    location_ids: List[str],
) -> Dict[str, Any]:
    """Cross-location benchmark comparison."""
    results = {}
    for lid in location_ids:
        bm = benchmark_processes(conn, lid)
        results[lid] = bm

    comparison = {"locations": results, "summary": {}}
    all_entity_types = set()
    for bm_list in results.values():
        for b in bm_list:
            all_entity_types.add(b["entity_type"])

    for etype in sorted(all_entity_types):
        conf_values = []
        cycle_values = []
        for lid, bm_list in results.items():
            for b in bm_list:
                if b["entity_type"] == etype:
                    if b["conformance_ratio"] is not None:
                        conf_values.append(b["conformance_ratio"])
                    if b["avg_cycle_time_days"] is not None:
                        cycle_values.append(b["avg_cycle_time_days"])

        summary = {"entity_type": etype}
        if conf_values:
            summary["avg_conformance"] = round(sum(conf_values) / len(conf_values), 4)
            summary["min_conformance"] = round(min(conf_values), 4)
            summary["max_conformance"] = round(max(conf_values), 4)
        if cycle_values:
            summary["avg_cycle_time_days"] = round(sum(cycle_values) / len(cycle_values), 4)
            summary["min_cycle_time_days"] = round(min(cycle_values), 4)
            summary["max_cycle_time_days"] = round(max(cycle_values), 4)
        comparison["summary"][etype] = summary

    return comparison


def process_roi(
    conn,
    process_key: str,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """ROI = (value of published outputs - process cost) / process cost.

    Value is estimated from the number of published instances times a
    standard value per published output (configurable).
    """
    VALUE_PER_OUTPUT = {
        "farm_operations": 15.0,
        "harvest_management": 50.0,
        "data_publication": 25.0,
        "impact_verification": 100.0,
        "metric_governance": 10.0,
        "work_management": 20.0,
        "stakeholder_feedback": 15.0,
        "agent_execution": 30.0,
        "reporting": 20.0,
    }

    value_per = VALUE_PER_OUTPUT.get(process_key, 10.0)

    cost_info = total_process_cost(conn, process_key, location_id)
    total_cost = sum(
        c["total_cost"] for c in cost_info.get("by_currency", [])
    )

    from services.analytics import process_mining as pm
    entity_map = {
        "farm_operations": "farm_activity",
        "harvest_management": "harvest_event",
        "data_publication": "data_stream_post",
        "impact_verification": "impact_claim",
        "metric_governance": "metric_value",
        "work_management": "work_item",
        "stakeholder_feedback": "stakeholder_feedback",
        "agent_execution": "agent_task",
        "reporting": "report_snapshot",
    }
    etype = entity_map.get(process_key)
    published_count = 0
    if etype:
        traces = pm.get_traces(conn, entity_type=etype)
        model = pm.load_model(conn, etype)
        goal = pm.goal_state(model)
        if goal:
            for (_e, _id), trace in traces.items():
                seq = [t["to_status"] for t in trace]
                if seq and seq[-1] == goal:
                    published_count += 1

    total_value = published_count * value_per
    roi = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else None

    return {
        "process_key": process_key,
        "published_instances": published_count,
        "value_per_instance": value_per,
        "total_estimated_value": round(total_value, 2),
        "total_process_cost": round(total_cost, 4),
        "roi_pct": round(roi, 1) if roi is not None else None,
    }


def create_improvement(
    conn,
    process_key: str,
    initiative_name: str,
    description: Optional[str] = None,
    improvement_type: Optional[str] = None,
    owner_id=None,
    location_id=None,
    due_at=None,
) -> Dict[str, Any]:
    """Create a Kaizen/improvement initiative."""
    sql = """
        INSERT INTO process_improvement
            (process_key, initiative_name, description, improvement_type,
             status, owner_id, location_id, due_at)
        VALUES (%s, %s, %s, %s, 'proposed', %s, %s, %s)
        RETURNING *
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (
            process_key, initiative_name, description, improvement_type,
            owner_id, location_id, due_at,
        ))
        conn.commit()
        return _row_to_dict(cur.fetchone())


def list_improvements(
    conn,
    process_key: Optional[str] = None,
    location_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List improvement initiatives."""
    clauses = []
    params: List[Any] = []
    if process_key:
        clauses.append("process_key = %s")
        params.append(process_key)
    if location_id:
        clauses.append("location_id = %s")
        params.append(location_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f"SELECT * FROM process_improvement WHERE {where} ORDER BY created_at DESC"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [_row_to_dict(r) for r in cur.fetchall()]


def complete_improvement(
    conn,
    improvement_id,
    actual_benefit: str,
) -> Dict[str, Any]:
    """Mark improvement as completed."""
    sql = """
        UPDATE process_improvement
        SET status = 'completed', actual_benefit = %s, completed_at = NOW()
        WHERE id = %s::uuid
        RETURNING *
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (actual_benefit, str(improvement_id)))
        conn.commit()
        r = cur.fetchone()
        return _row_to_dict(r) if r else {}
