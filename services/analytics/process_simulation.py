"""Process simulation and what-if analysis service.

Creates simulation scenarios, applies parameter overrides, computes
projected outcomes, and compares against targets and maturity levels.

Schema: 193_process_simulation.sql
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db
from services.analytics import process_mining as pm, value_stream
from services.analytics.process_gap import (
    _compute_actual, _compute_gap, _assign_maturity,
    _has_workflow_spec, _has_conformance, _has_spc, _has_feedback,
)


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


def create_simulation(
    conn,
    name: str,
    scenario_params: Dict[str, Any],
    description: Optional[str] = None,
    process_key: Optional[str] = None,
    created_by=None,
    location_id=None,
) -> Dict[str, Any]:
    """Create a what-if simulation scenario."""
    import json
    sql = """
        INSERT INTO process_simulation
            (name, description, process_key, scenario_params, status,
             created_by, location_id)
        VALUES (%s, %s, %s, %s, 'draft', %s, %s)
        RETURNING *
    """
    # Validate created_by as UUID or set None
    cb = None
    if created_by is not None:
        try:
            cb = str(uuid.UUID(str(created_by)))
        except (ValueError, AttributeError):
            cb = None

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (
            name, description, process_key,
            psycopg2.extras.Json(scenario_params),
            cb, location_id,
        ))
        conn.commit()
        return _row_to_dict(cur.fetchone())


def run_simulation(
    conn,
    simulation_id: str,
) -> Dict[str, Any]:
    """Run a simulation by applying scenario parameters to baseline metrics.

    Steps:
    1. Load current baseline metrics (lead time, FTY, cost, cycle time)
    2. Apply scenario parameters (e.g., 20% lead time reduction)
    3. Compute projected outcomes
    4. Compare against targets (gap analysis with simulated values)
    5. Compute simulated maturity level
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM process_simulation WHERE id = %s::uuid", (simulation_id,))
    sim = cur.fetchone()
    if not sim:
        return {"error": "simulation not found"}

    sim = dict(sim)
    params = sim.get("scenario_params", {})
    process_key = sim.get("process_key")

    # Mark as running
    cur.execute(
        "UPDATE process_simulation SET status = 'running' WHERE id = %s::uuid",
        (simulation_id,),
    )
    conn.commit()

    try:
        # 1. Load baseline metrics
        baseline = {}
        if process_key:
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
            if etype:
                for metric in ("lead_time_days", "fty_pct", "cycle_time_days", "rework_rate_pct"):
                    val = _compute_actual(conn, etype, metric)
                    if val is not None:
                        baseline[metric] = val

            # Load cost baseline
            cur.execute("""
                SELECT COALESCE(SUM(cost_amount), 0) AS total_cost
                FROM process_cost_observation WHERE process_key = %s
            """, (process_key,))
            row = cur.fetchone()
            if row:
                baseline["total_cost"] = float(row["total_cost"])

            # Load instance count
            if etype:
                traces = pm.get_traces(conn, entity_type=etype)
                baseline["instance_count"] = len(traces)

        # 2. Apply scenario parameters
        simulated = dict(baseline)
        lt_reduction = params.get("lead_time_reduction_pct", 0) / 100.0
        fty_improvement = params.get("fty_improvement_pct", 0) / 100.0
        cost_reduction = params.get("cost_reduction_pct", 0) / 100.0
        automation_pct = params.get("automation_pct", 0)
        staff_increase = params.get("staff_increase", 0)

        if "lead_time_days" in simulated:
            simulated["lead_time_days"] = round(
                simulated["lead_time_days"] * (1 - lt_reduction), 4
            )
        if "cycle_time_days" in simulated:
            simulated["cycle_time_days"] = round(
                simulated["cycle_time_days"] * (1 - lt_reduction), 4
            )
        if "fty_pct" in simulated:
            simulated["fty_pct"] = round(
                min(100.0, simulated["fty_pct"] * (1 + fty_improvement)), 4
            )
        if "rework_rate_pct" in simulated:
            simulated["rework_rate_pct"] = round(
                max(0.0, simulated["rework_rate_pct"] * (1 - fty_improvement)), 4
            )
        if "total_cost" in simulated:
            automation_savings = automation_pct * 0.3
            staff_cost = staff_increase * 0.1
            simulated["total_cost"] = round(
                simulated["total_cost"] * (1 - cost_reduction - automation_savings + staff_cost), 4
            )

        # 3. Compute improvement percentages
        results = []
        for metric, base_val in baseline.items():
            if metric in simulated and base_val != 0:
                sim_val = simulated[metric]
                improvement = round(100.0 * (sim_val - base_val) / abs(base_val), 2)
                results.append({
                    "metric_name": metric,
                    "baseline_value": base_val,
                    "simulated_value": sim_val,
                    "improvement_pct": improvement,
                })

        # 4. Compare against targets
        target_comparison = []
        if process_key:
            cur.execute(
                "SELECT * FROM process_target WHERE process_key = %s",
                (process_key,),
            )
            targets = [_row_to_dict(r) for r in cur.fetchall()]
            for target in targets:
                etype = target.get("entity_type")
                metric = target["metric_name"]
                target_val = target["target_value"]
                direction = target.get("target_direction", "lte")
                actual = _compute_actual(conn, etype, metric)
                sim_actual = simulated.get(metric)

                base_gap = None
                sim_gap = None
                if actual is not None:
                    base_gap, _ = _compute_gap(target_val, actual, direction)
                if sim_actual is not None:
                    sim_gap, _ = _compute_gap(target_val, sim_actual, direction)

                target_comparison.append({
                    "metric_name": metric,
                    "target_value": target_val,
                    "direction": direction,
                    "baseline_actual": actual,
                    "baseline_gap": base_gap,
                    "simulated_actual": sim_actual,
                    "simulated_gap": sim_gap,
                    "gap_improvement": (
                        round(base_gap - sim_gap, 4)
                        if base_gap is not None and sim_gap is not None
                        else None
                    ),
                })

        # 5. Compute simulated maturity
        has_spec = _has_workflow_spec(process_key) if process_key else False
        has_conformance, conf_ratio = _has_conformance(conn, process_key) if process_key else (False, None)
        has_spc = _has_spc(conn, process_key)
        has_feedback = _has_feedback(conn)

        avg_gap_pct = None
        if target_comparison:
            gaps = [abs(t["simulated_gap"]) for t in target_comparison if t["simulated_gap"] is not None]
            if gaps:
                avg_gap_pct = sum(gaps) / len(gaps)

        sim_level, sim_name = _assign_maturity(
            avg_gap_pct, has_spec, has_conformance, conf_ratio,
            has_spc, True, has_feedback,
        )

        # Persist results
        for r in results:
            cur.execute("""
                INSERT INTO process_simulation_result
                    (simulation_id, metric_name, baseline_value, simulated_value,
                     improvement_pct, confidence)
                VALUES (%s::uuid, %s, %s, %s, %s, 0.85)
            """, (
                simulation_id, r["metric_name"], r["baseline_value"],
                r["simulated_value"], r["improvement_pct"],
            ))

        # Update simulation
        sim_results = {
            "baseline": baseline,
            "simulated": simulated,
            "results": results,
            "target_comparison": target_comparison,
            "simulated_maturity": {"level": sim_level, "level_name": sim_name},
            "scenario_params": params,
        }
        cur.execute("""
            UPDATE process_simulation
            SET status = 'completed', results = %s, completed_at = NOW()
            WHERE id = %s::uuid
        """, (psycopg2.extras.Json(sim_results), simulation_id))
        conn.commit()

        return {
            "simulation_id": simulation_id,
            "status": "completed",
            **sim_results,
        }

    except Exception as e:
        conn.rollback()
        cur.execute(
            "UPDATE process_simulation SET status = 'cancelled' WHERE id = %s::uuid",
            (simulation_id,),
        )
        conn.commit()
        return {"simulation_id": simulation_id, "status": "failed", "error": str(e)}


def list_simulations(
    conn,
    process_key: Optional[str] = None,
    location_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List simulation scenarios."""
    clauses = []
    params = []
    if process_key:
        clauses.append("process_key = %s")
        params.append(process_key)
    if location_id:
        clauses.append("location_id = %s")
        params.append(location_id)
    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f"SELECT * FROM process_simulation WHERE {where} ORDER BY created_at DESC"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_simulation_results(
    conn,
    simulation_id: str,
) -> Dict[str, Any]:
    """Returns simulation results with comparison."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM process_simulation WHERE id = %s::uuid", (simulation_id,))
    sim = cur.fetchone()
    if not sim:
        return {"error": "simulation not found"}

    cur.execute(
        "SELECT * FROM process_simulation_result WHERE simulation_id = %s::uuid ORDER BY metric_name",
        (simulation_id,),
    )
    results = [_row_to_dict(r) for r in cur.fetchall()]

    return {
        "simulation": _row_to_dict(sim),
        "metric_results": results,
    }


def simulate_bottleneck_relief(
    conn,
    entity_type: str,
    relief_pct: float,
) -> Dict[str, Any]:
    """Simulate what happens if bottleneck WIP is reduced by relief_pct."""
    wip = value_stream.wip_by_stage(conn)
    relevant = [w for w in wip if w.get("entity_type") == entity_type]

    bottleneck = None
    max_wip = 0
    for w in relevant:
        stage_wip = w.get("wip_count", 0)
        if stage_wip > max_wip:
            max_wip = stage_wip
            bottleneck = w

    if not bottleneck:
        return {"entity_type": entity_type, "error": "no bottleneck found"}

    current_wip = bottleneck.get("wip_count", 0)
    reduced_wip = round(current_wip * (1 - relief_pct / 100.0))
    wip_reduction = current_wip - reduced_wip

    estimated_lead_time_reduction = round(relief_pct * 0.7, 2)

    return {
        "entity_type": entity_type,
        "bottleneck_stage": bottleneck.get("status"),
        "current_wip": current_wip,
        "reduced_wip": reduced_wip,
        "wip_reduction": wip_reduction,
        "relief_pct": relief_pct,
        "estimated_lead_time_reduction_pct": estimated_lead_time_reduction,
    }


def simulate_automation_impact(
    conn,
    process_key: str,
    automation_pct: float,
) -> Dict[str, Any]:
    """Simulate impact of automating a percentage of process steps."""
    from services.analytics.process_costing import process_cost_per_instance, total_process_cost

    cost_info = process_cost_per_instance(conn, process_key)
    total_cost = cost_info.get("total_cost", 0)

    labor_cost = 0
    for ct in cost_info.get("by_cost_type", []):
        if ct.get("cost_type") == "labor":
            labor_cost = ct.get("total_cost", 0)

    automated_labor = round(labor_cost * automation_pct, 4)
    cost_savings = round(automated_labor * 0.5, 4)
    new_total_cost = round(total_cost - cost_savings, 4)

    speed_improvement = round(automation_pct * 15.0, 2)

    return {
        "process_key": process_key,
        "automation_pct": automation_pct,
        "current_total_cost": total_cost,
        "current_labor_cost": labor_cost,
        "automated_labor_cost": round(automated_labor, 4),
        "estimated_cost_savings": cost_savings,
        "projected_total_cost": new_total_cost,
        "estimated_speed_improvement_pct": speed_improvement,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    import json
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Process simulation and what-if analysis")
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create")
    create_p.add_argument("--name", required=True)
    create_p.add_argument("--description", default=None)
    create_p.add_argument("--process-key", default=None)
    create_p.add_argument("--location-id", default=None)
    create_p.add_argument("--params", default="{}",
                          help="JSON dict of scenario parameters")
    create_p.add_argument("--created-by", default=None)

    run_p = sub.add_parser("run")
    run_p.add_argument("--simulation-id", required=True)

    list_p = sub.add_parser("list")
    list_p.add_argument("--process-key", default=None)
    list_p.add_argument("--location-id", default=None)

    get_p = sub.add_parser("get")
    get_p.add_argument("--simulation-id", required=True)

    bn_p = sub.add_parser("bottleneck")
    bn_p.add_argument("--entity-type", required=True)
    bn_p.add_argument("--relief-pct", type=float, default=30.0)

    auto_p = sub.add_parser("automation")
    auto_p.add_argument("--process-key", required=True)
    auto_p.add_argument("--pct", type=float, default=20.0,
                        help="Percentage of process to automate (0-100)")

    args = parser.parse_args()
    conn = _conn()
    try:
        if args.command == "create":
            params = json.loads(args.params)
            out = create_simulation(
                conn, args.name, params,
                description=args.description,
                process_key=args.process_key,
                created_by=args.created_by,
                location_id=args.location_id,
            )
        elif args.command == "run":
            out = run_simulation(conn, args.simulation_id)
        elif args.command == "list":
            out = list_simulations(conn, args.process_key, args.location_id)
        elif args.command == "get":
            out = get_simulation_results(conn, args.simulation_id)
        elif args.command == "bottleneck":
            out = simulate_bottleneck_relief(conn, args.entity_type, args.relief_pct)
        elif args.command == "automation":
            out = simulate_automation_impact(conn, args.process_key, args.pct)
        else:
            out = {"error": "unknown command"}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
