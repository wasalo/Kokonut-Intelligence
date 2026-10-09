"""Process-health board (BPM Monitor / BAM).

Assembles a single process-health view across the governed publication
pipeline by combining VSM metrics (WIP, lead time, FTY, bottlenecks),
process-mining conformance, optional predictive-breach risk, and
CMMI-inspired maturity assessments. Registered as the `process_health`
report type and exposed via a CLI board command.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from services.common.database import get_db
from services.analytics import value_stream, process_mining as pm, predictive_bpm
from services.analytics.process_gap import assess_maturity
from services.common.cli import print_json

DEFAULT_SLA_HOURS = 72.0


def _count_instances(conn, entity_type: str) -> int:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT entity_id) FROM lifecycle_transition WHERE entity_type = %s",
        (entity_type,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0


def _conformance(conn) -> List[Dict[str, Any]]:
    out = []
    for etype in value_stream.INSTRUMENTED_TYPES:
        total = _count_instances(conn, etype)
        if total == 0:
            continue
        findings = pm.check_conformance(conn, etype)
        nonconf = len(findings)
        ratio = round(1.0 - nonconf / total, 4) if total else None
        out.append(
            {
                "entity_type": etype,
                "total_instances": total,
                "nonconforming_traces": nonconf,
                "conformance_ratio": ratio,
            }
        )
    return out


def build_health(
    conn,
    location_id: Optional[str] = None,
    sla_target_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """Assemble the process-health board across all instrumented entity types."""
    # Model-driven VSM lead time + first-time-through yield (per entity type).
    lead_times: List[Dict[str, Any]] = []
    fty: Dict[str, Any] = {}
    for etype, _col in value_stream._PIPELINE:
        model = pm.load_model(conn, etype)
        goal = pm.goal_state(model) or "published"
        init = pm.initial_state(model) or "draft"
        fail = pm.fail_state(model)
        lead_times += value_stream.stage_lead_times(
            conn, location_id, initial_status=init, goal_status=goal, entity_type=etype
        )
        fty[etype] = value_stream.first_time_through(
            conn, location_id, goal_status=goal,
            fail_status=fail, entity_type=etype,
        )

    health: Dict[str, Any] = {
        "scope": {"location_id": location_id},
        "wip_by_stage": value_stream.wip_by_stage(conn, location_id),
        "stage_lead_times_days": lead_times,
        "first_time_through_yield": fty,
        "bottleneck_ranking": value_stream.bottleneck_ranking(conn, location_id),
        "conformance": _conformance(conn),
    }
    if sla_target_hours:
        risk = []
        for etype in value_stream.INSTRUMENTED_TYPES:
            found = predictive_bpm.breaches(conn, etype, sla_target_hours)
            if found:
                risk.append({"entity_type": etype, "at_risk": len(found)})
        health["breach_risk"] = {
            "sla_target_hours": sla_target_hours,
            "at_risk_by_type": risk,
        }

    # Maturity assessments per process
    maturity = {}
    process_keys = [
        "farm_operations", "harvest_management", "data_publication",
        "impact_verification", "metric_governance", "work_management",
        "event_delivery", "stakeholder_feedback", "agent_execution",
        "reporting",
    ]
    for pk in process_keys:
        try:
            mat = assess_maturity(conn, pk)
            maturity[pk] = {
                "level": mat["level"],
                "level_name": mat["level_name"],
                "avg_gap_pct": mat.get("avg_gap_pct"),
            }
        except Exception:
            maturity[pk] = {"level": 1, "level_name": "Initial"}
    health["maturity"] = maturity

    return health


def generate_process_health(
    conn,
    location_id: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Report-generator compatible entry point (BAM board, no SLA breach risk)."""
    return build_health(conn, location_id=location_id, sla_target_hours=None)


# --- CLI --------------------------------------------------------------------

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "board":
            out = build_health(
                conn, args.location_id,
                sla_target_hours=args.sla_target_hours,
            )
        else:
            out = {}
        print_json(out)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process-health board (BAM)")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("board")
    b.add_argument("--location-id", default=None)
    b.add_argument("--sla-target-hours", type=float, default=None)
    args = parser.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
