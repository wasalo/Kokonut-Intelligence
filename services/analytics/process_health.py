"""Process-health board (BPM Monitor / BAM).

Assembles a single process-health view across the governed publication
pipeline by combining VSM metrics (WIP, lead time, FTY, bottlenecks),
process-mining conformance, and optional predictive-breach risk. Registered
as the `process_health` report type and exposed via a CLI board command.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from services.ingestion.base import get_db
from services.analytics import value_stream, process_mining, predictive_bpm


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
    for etype, _col in value_stream._PIPELINE:
        total = _count_instances(conn, etype)
        if total == 0:
            continue
        findings = process_mining.check_conformance(conn, etype)
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
    """Assemble the process-health board."""
    health: Dict[str, Any] = {
        "scope": {"location_id": location_id},
        "wip_by_stage": value_stream.wip_by_stage(conn, location_id),
        "stage_lead_times_days": value_stream.stage_lead_times(conn, location_id),
        "first_time_through_yield": value_stream.first_time_through(conn, location_id),
        "bottleneck_ranking": value_stream.bottleneck_ranking(conn, location_id),
        "conformance": _conformance(conn),
    }
    if sla_target_hours:
        risk = []
        for etype, _col in value_stream._PIPELINE:
            found = predictive_bpm.breaches(conn, etype, sla_target_hours)
            if found:
                risk.append({"entity_type": etype, "at_risk": len(found)})
        health["breach_risk"] = {
            "sla_target_hours": sla_target_hours,
            "at_risk_by_type": risk,
        }
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
        print(json.dumps(out, indent=2, default=str))
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
