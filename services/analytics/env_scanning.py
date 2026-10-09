"""Environmental Scanning Workflow service — 5-step governed scanning process."""

from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db
from services.common.logging import get_logger
from services.common.cli import print_json
logger = get_logger(__name__)

SCAN_TYPES = ("full", "quick", "focused", "update")
STEP_NAMES = ("identify", "gather", "analyze", "communicate", "decide")
STEP_DESCRIPTIONS = {
    1: "Identify — Identify emerging issues, trends, and signals",
    2: "Gather — Collect relevant data from platform sources",
    3: "Analyze — Analyze data, assess significance, detect patterns",
    4: "Communicate — Synthesize findings into actionable insights",
    5: "Decide — Recommend decisions and next steps",
}


def create_scan(
    conn,
    location_id: str,
    title: str,
    scan_type: str = "full",
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    if scan_type not in SCAN_TYPES:
        raise ValueError(f"scan_type must be one of {SCAN_TYPES}")

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO env_scan (location_id, title, scan_type, created_by)
               VALUES (%s, %s, %s, %s)
               RETURNING id, location_id, title, scan_type, current_step, status, created_at""",
            (location_id, title, scan_type, created_by),
        )
        scan = dict(cur.fetchone())

        for i, name in enumerate(STEP_NAMES, 1):
            cur.execute(
                """INSERT INTO env_scan_step (scan_id, location_id, step_number, step_name)
                   VALUES (%s, %s, %s, %s)""",
                (scan["id"], location_id, i, name),
            )
        conn.commit()
        logger.info("Created env scan %s (%s) for %s", scan["id"], scan_type, location_id)
        return scan


def update_step(
    conn,
    scan_id: str,
    step_number: int,
    status: Optional[str] = None,
    findings: Optional[str] = None,
    recommendations: Optional[str] = None,
    data_source: Optional[Dict] = None,
) -> Dict[str, Any]:
    if step_number < 1 or step_number > 5:
        raise ValueError("step_number must be 1-5")

    updates = []
    params = []
    if status:
        updates.append("status = %s")
        params.append(status)
        if status == "in_progress":
            updates.append("started_at = COALESCE(started_at, now())")
        elif status == "completed":
            updates.append("completed_at = now()")
    if findings is not None:
        updates.append("findings = %s")
        params.append(findings)
    if recommendations is not None:
        updates.append("recommendations = %s")
        params.append(recommendations)
    if data_source is not None:
        updates.append("data_source = %s")
        params.append(json.dumps(data_source))

    if not updates:
        return {}

    params.extend([scan_id, step_number])

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""UPDATE env_scan_step SET {', '.join(updates)}
                WHERE scan_id = %s AND step_number = %s
                RETURNING id, step_name, status, findings""",
            params,
        )
        row = cur.fetchone()

        cur.execute(
            """SELECT COUNT(*) AS completed
               FROM env_scan_step
               WHERE scan_id = %s AND status = 'completed'""",
            (scan_id,),
        )
        completed = (cur.fetchone() or {}).get("completed", 0) or 0

        next_step = min(5, completed + 1) if completed < 5 else 5
        new_scan_status = "completed" if completed >= 5 else "in_progress" if completed > 0 else "draft"

        cur.execute(
            """UPDATE env_scan
               SET completed_steps = %s, current_step = %s, status = %s, updated_at = now()
               WHERE id = %s""",
            (completed, next_step, new_scan_status, scan_id),
        )
        conn.commit()
        return dict(row) if row else {}


def get_scan(conn, scan_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT es.*, l.name AS location_name
               FROM env_scan es
               LEFT JOIN location l ON l.id = es.location_id
               WHERE es.id = %s""",
            (scan_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        result = dict(row)

        cur.execute(
            """SELECT * FROM env_scan_step
               WHERE scan_id = %s ORDER BY step_number""",
            (scan_id,),
        )
        result["steps"] = [dict(r) for r in cur.fetchall()]
        return result


def list_scans(conn, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if location_id:
            cur.execute(
                """SELECT es.*, l.name AS location_name
                   FROM env_scan es
                   LEFT JOIN location l ON l.id = es.location_id
                   WHERE es.location_id = %s
                   ORDER BY es.created_at DESC""",
                (location_id,),
            )
        else:
            cur.execute(
                """SELECT es.*, l.name AS location_name
                   FROM env_scan es
                   LEFT JOIN location l ON l.id = es.location_id
                   ORDER BY es.created_at DESC"""
            )
        return [dict(r) for r in cur.fetchall()]


def complete_scan(conn, scan_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE env_scan SET status = 'completed', completed_steps = 5,
               updated_at = now() WHERE id = %s
               RETURNING id, title, status""",
            (scan_id,),
        )
        row = cur.fetchone()
        cur.execute(
            """UPDATE env_scan_step SET status = 'completed', completed_at = now()
               WHERE scan_id = %s AND status != 'completed'""",
            (scan_id,),
        )
        conn.commit()
        return dict(row) if row else {}


def auto_populate(conn, scan_id: str) -> Dict[str, Any]:
    scan = get_scan(conn, scan_id)
    if not scan:
        raise ValueError(f"Scan {scan_id} not found")
    location_id = scan["location_id"]
    results: Dict[str, Any] = {}

    # Step 1: Identify — query threatcasting signals and stakeholder feedback
    findings_1 = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT name, severity, description FROM threat
                   WHERE location_id = %s AND status IN ('active', 'monitored')
                   ORDER BY
                     CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                                   WHEN 'moderate' THEN 3 ELSE 4 END
                   LIMIT 10""",
                (location_id,),
            )
            for r in cur.fetchall():
                findings_1.append(f"Threat: {r['name']} (severity: {r['severity']})")
    except psycopg2.Error:
        conn.rollback()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT stakeholder_group, COUNT(*) AS cnt, sentiment
                   FROM stakeholder_feedback
                   WHERE location_id = %s
                   GROUP BY stakeholder_group, sentiment
                   HAVING sentiment = 'negative'
                   LIMIT 5""",
                (location_id,),
            )
            for r in cur.fetchall():
                findings_1.append(f"Negative feedback from {r['stakeholder_group']} ({r['cnt']} signals)")
    except psycopg2.Error:
        conn.rollback()

    if findings_1:
        update_step(conn, scan_id, 1, status="completed",
                    findings="\n".join(findings_1),
                    recommendations="Review high-severity threats; engage dissatisfied stakeholders")
    results["step_1"] = {"evidence_count": len(findings_1)}

    # Step 2: Gather — query PESTEL factors, market data, weather
    findings_2 = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT category, COUNT(*) AS cnt, AVG(impact_score) AS avg_impact
                   FROM pestel_factor
                   WHERE location_id = %s
                   GROUP BY category""",
                (location_id,),
            )
            for r in cur.fetchall():
                findings_2.append(f"PESTEL {r['category']}: {r['cnt']} factors (avg impact {float(r['avg_impact']):.1f})")
    except psycopg2.Error:
        conn.rollback()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT commodity, AVG(price) AS avg_price, COUNT(*) AS obs
                   FROM market_price_observation
                   WHERE location_id = %s
                   GROUP BY commodity""",
                (location_id,),
            )
            for r in cur.fetchall():
                findings_2.append(f"Market: {r['commodity']} avg {float(r['avg_price']):.2f} ({r['obs']} obs)")
    except psycopg2.Error:
        conn.rollback()

    if findings_2:
        update_step(conn, scan_id, 2, status="completed",
                    findings="\n".join(findings_2),
                    recommendations="Cross-reference market data with PESTEL risk factors")
    results["step_2"] = {"evidence_count": len(findings_2)}

    # Step 3: Analyze — query CRISP scores, metrics
    findings_3 = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT composite_score, rating, confidence_level
                   FROM crisp_risk_assessment
                   WHERE location_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (location_id,),
            )
            row = cur.fetchone()
            if row:
                findings_3.append(f"CRISP: {row['rating']} (score {row['composite_score']}, confidence {row['confidence_level']})")
    except psycopg2.Error:
        conn.rollback()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT metric_name, value, verified
                   FROM metric_value
                   WHERE location_id = %s
                   ORDER BY computed_at DESC LIMIT 5""",
                (location_id,),
            )
            for r in cur.fetchall():
                vstatus = "verified" if r["verified"] else "draft"
                findings_3.append(f"Metric: {r['metric_name']} = {r['value']} ({vstatus})")
    except psycopg2.Error:
        conn.rollback()

    if findings_3:
        update_step(conn, scan_id, 3, status="completed",
                    findings="\n".join(findings_3),
                    recommendations="Focus on high-risk CRISP dimensions; verify draft metrics")
    results["step_3"] = {"evidence_count": len(findings_3)}

    # Step 4: Communicate — generate summary from all steps
    all_findings = []
    for step in scan.get("steps", []):
        if step.get("findings"):
            all_findings.append(f"Step {step['step_number']} ({step['step_name']}): {step['findings'][:200]}")

    if all_findings:
        update_step(conn, scan_id, 4, status="completed",
                    findings="\n\n".join(all_findings),
                    recommendations="Prepare briefing for stakeholders; update decision policies")
    results["step_4"] = {"evidence_count": len(all_findings)}

    # Step 5: Decide — query decision policies and advisory
    findings_5 = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT rule_name, rule_type, requires_approval
                   FROM decision_policy
                   WHERE status = 'active'
                   LIMIT 5""",
            )
            for r in cur.fetchall():
                findings_5.append(f"Policy: {r['rule_name']} ({r['rule_type']}, approval={'yes' if r['requires_approval'] else 'no'})")
    except psycopg2.Error:
        conn.rollback()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT recommendation_type, title, priority
                   FROM advisory_recommendation
                   WHERE location_id = %s AND status = 'pending'
                   ORDER BY
                     CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                                   WHEN 'medium' THEN 3 ELSE 4 END
                   LIMIT 5""",
                (location_id,),
            )
            for r in cur.fetchall():
                findings_5.append(f"Advisory: {r['title']} (priority: {r['priority']})")
    except psycopg2.Error:
        conn.rollback()

    if findings_5:
        update_step(conn, scan_id, 5, status="completed",
                    findings="\n".join(findings_5),
                    recommendations="Execute pending advisories; review decision policies")
    results["step_5"] = {"evidence_count": len(findings_5)}

    logger.info("Auto-populated scan %s with %d total findings",
                scan_id, sum(r["evidence_count"] for r in results.values()))
    return results


def render_markdown(scan: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Environmental Scan: {scan.get('title', 'Untitled')}\n")
    lines.append(f"**Location:** {scan.get('location_name', 'N/A')}")
    lines.append(f"**Type:** {scan.get('scan_type', 'full')}")
    lines.append(f"**Status:** {scan.get('status', 'draft')}")
    lines.append(f"**Progress:** {scan.get('completed_steps', 0)}/{scan.get('total_steps', 5)} steps\n")

    for step in scan.get("steps", []):
        status_icon = "[x]" if step["status"] == "completed" else "[ ]"
        lines.append(f"## {status_icon} Step {step['step_number']}: {step['step_name'].title()}\n")
        if step.get("findings"):
            lines.append("**Findings:**")
            for finding in step["findings"].split("\n"):
                if finding.strip():
                    lines.append(f"- {finding.strip()}")
        if step.get("recommendations"):
            lines.append(f"\n**Recommendations:** {step['recommendations']}")
        lines.append("")

    return "\n".join(lines)


def render_cli(scan: Dict[str, Any]) -> str:
    w = 78
    lines = []
    lines.append("=" * w)
    lines.append(f"  ENVIRONMENTAL SCAN: {scan.get('title', 'Untitled').upper()}")
    lines.append("=" * w)
    lines.append(f"  Location:  {scan.get('location_name', 'N/A')}")
    lines.append(f"  Type:      {scan.get('scan_type', 'full')}")
    lines.append(f"  Status:    {scan.get('status', 'draft')}")
    lines.append(f"  Progress:  {scan.get('completed_steps', 0)}/{scan.get('total_steps', 5)} steps")
    lines.append("-" * w)

    for step in scan.get("steps", []):
        status_icon = "[x]" if step["status"] == "completed" else "[ ]"
        lines.append(f"\n  {status_icon} Step {step['step_number']}: {step['step_name'].upper()}")
        if step.get("findings"):
            for finding in step["findings"].split("\n")[:5]:
                if finding.strip():
                    lines.append(f"    - {finding.strip()[:70]}")
        if step.get("recommendations"):
            recs = step["recommendations"][:70]
            lines.append(f"    -> {recs}")

    lines.append("\n" + "=" * w)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Environmental Scanning CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", help="Create scan")
    p.add_argument("--location-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--type", dest="scan_type", default="full", choices=list(SCAN_TYPES))

    p = sub.add_parser("update-step", help="Update a step")
    p.add_argument("--scan-id", required=True)
    p.add_argument("--step", type=int, required=True, choices=[1, 2, 3, 4, 5])
    p.add_argument("--status")
    p.add_argument("--findings")
    p.add_argument("--recommendations")

    p = sub.add_parser("get", help="Get scan")
    p.add_argument("--scan-id", required=True)

    p = sub.add_parser("list", help="List scans")
    p.add_argument("--location-id")

    p = sub.add_parser("complete", help="Complete scan")
    p.add_argument("--scan-id", required=True)

    p = sub.add_parser("auto-populate", help="Auto-populate steps from platform data")
    p.add_argument("--scan-id", required=True)

    p = sub.add_parser("export", help="Export scan as markdown")
    p.add_argument("--scan-id", required=True)

    args = parser.parse_args()
    conn = get_db()
    try:
        if args.command == "create":
            result = create_scan(conn, args.location_id, args.title, args.scan_type)
        elif args.command == "update-step":
            result = update_step(conn, args.scan_id, args.step, args.status, args.findings, args.recommendations)
        elif args.command == "get":
            result = get_scan(conn, args.scan_id)
        elif args.command == "list":
            result = list_scans(conn, args.location_id)
        elif args.command == "complete":
            result = complete_scan(conn, args.scan_id)
        elif args.command == "auto-populate":
            result = auto_populate(conn, args.scan_id)
        elif args.command == "export":
            scan = get_scan(conn, args.scan_id)
            if scan:
                print(render_markdown(scan))
                return
            result = {"error": "scan not found"}
        else:
            result = {"error": "unknown command"}
        print_json(result)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
