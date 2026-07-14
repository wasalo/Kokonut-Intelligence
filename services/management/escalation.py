"""Process auto-escalation / handover (BPM human-interaction phase).

When a governed process instance is predicted to breach its SLA, raise an
escalation: record it in process_escalation and (optionally) create a draft
work_item for human follow-up. Idempotent per open instance. Never verifies
or publishes anything (agents/handlers stay read/draft-only).

Reads lifecycle_transition via predictive_bpm; writes process_escalation
(and optionally work_item via services.management.workbench).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

# workbench.create_work_item passes uuid.UUID parameters; ensure psycopg2
# can adapt them in every environment.
psycopg2.extras.register_uuid()

from services.ingestion.base import get_db
from services.analytics import predictive_bpm as pp


def _distinct_entity_types(conn) -> List[str]:
    """Every governed entity type actually present in the lifecycle ledger."""
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT entity_type FROM lifecycle_transition")
    return [r[0] for r in cur.fetchall()]


def find_at_risk(
    conn, sla_target_hours: float, threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """All in-flight instances predicted to breach the SLA across governed types."""
    at_risk: List[Dict[str, Any]] = []
    for etype in _distinct_entity_types(conn):
        for f in pp.breaches(conn, etype, sla_target_hours, threshold):
            at_risk.append(
                {
                    "entity_type": etype,
                    "entity_id": f["entity_id"],
                    "breach_probability": f["breach_probability"],
                    "predicted_total_hours": f.get("predicted_total_hours"),
                }
            )
    return at_risk


def _open_escalation(conn, entity_type: str, entity_id: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """SELECT 1 FROM process_escalation
           WHERE entity_type = %s AND entity_id = %s AND resolved_at IS NULL""",
        (entity_type, entity_id),
    )
    return cur.fetchone() is not None


def sweep_and_escalate(
    conn,
    sla_target_hours: float = 72.0,
    threshold: float = 0.5,
    org_id: Optional[str] = None,
    created_by_type: str = "system",
) -> int:
    """Raise escalations for at-risk instances; idempotent per open instance."""
    at_risk = find_at_risk(conn, sla_target_hours, threshold)
    created = 0
    for r in at_risk:
        if _open_escalation(conn, r["entity_type"], r["entity_id"]):
            continue
        work_item_id = None
        if org_id:
            from services.management import workbench

            sla_at = (datetime.now(timezone.utc) + timedelta(hours=sla_target_hours)).isoformat()
            wi = workbench.create_work_item(
                conn,
                org_id,
                title=f"Process SLA risk: {r['entity_type']} {r['entity_id']}",
                created_by_type=created_by_type,
                description=(
                    f"Predicted SLA-breach probability {r['breach_probability']}; "
                    f"predicted total {r['predicted_total_hours']}h (SLA {sla_target_hours}h)."
                ),
                priority="high",
                sla_at=sla_at,
            )
            work_item_id = str(wi["id"])
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO process_escalation
                (entity_type, entity_id, work_item_id, reason, breach_probability, escalated_to)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                r["entity_type"],
                r["entity_id"],
                work_item_id,
                f"SLA breach risk (prob={r['breach_probability']})",
                r["breach_probability"],
                None,
            ),
        )
        created += 1
    conn.commit()
    return created


def resolve_escalation(conn, escalation_id: str, resolved_by: Optional[str] = None) -> int:
    """Mark an escalation resolved (human action)."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE process_escalation SET resolved_at = now() WHERE id = %s AND resolved_at IS NULL",
        (escalation_id,),
    )
    n = cur.rowcount
    conn.commit()
    return n


# --- CLI --------------------------------------------------------------------

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "sweep":
            out = {
                "created": sweep_and_escalate(
                    conn, args.sla_target_hours, args.threshold, args.org_id,
                )
            }
        elif args.command == "resolve":
            out = {"resolved": resolve_escalation(conn, args.escalation_id, args.resolved_by)}
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process auto-escalation")
    sub = parser.add_subparsers(dest="command", required=True)
    sw = sub.add_parser("sweep")
    sw.add_argument("--org-id", default=None)
    sw.add_argument("--sla-target-hours", type=float, default=72.0)
    sw.add_argument("--threshold", type=float, default=0.5)
    rs = sub.add_parser("resolve")
    rs.add_argument("--escalation-id", required=True)
    rs.add_argument("--resolved-by", default=None)
    args = parser.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
