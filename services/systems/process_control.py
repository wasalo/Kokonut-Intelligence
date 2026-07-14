"""Statistical process control over process KPIs (BPM Optimize phase).

Computes control limits on process KPIs (cycle time, first-time-through
yield, rework rate) derived from the lifecycle ledger, detects
out-of-control points, and reports CTQ conformance. Pairs with
process_mining (variant/cycle-time source) and value_stream (FTY source).

Reads lifecycle_transition; writes process_kpi_snapshot when capturing.
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db


def control_limits(values: List[float], k: float = 3.0) -> Dict[str, float]:
    """Return mean, sample stdev, UCL/LCL (mean +/- k*sigma), and 2-sigma warns."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": 0.0, "sd": 0.0, "ucl": 0.0, "lcl": 0.0,
                "warn_high": 0.0, "warn_low": 0.0}
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mean, 6),
        "sd": round(sd, 6),
        "ucl": round(mean + k * sd, 6),
        "lcl": round(mean - k * sd, 6),
        "warn_high": round(mean + 2 * sd, 6),
        "warn_low": round(mean - 2 * sd, 6),
    }


def _distinct_types(conn) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT entity_type FROM lifecycle_transition")
    return [r[0] for r in cur.fetchall()]


def _cycle_time_mean(conn, entity_type: str) -> Optional[float]:
    """Mean draft->published days for published instances of this type."""
    cur = conn.cursor()
    cur.execute(
        """
        WITH start AS (
            SELECT entity_id, MIN(transitioned_at) AS s
            FROM lifecycle_transition
            WHERE entity_type = %s AND (from_status = 'draft' OR to_status = 'draft')
            GROUP BY entity_id
        ),
        pub AS (
            SELECT entity_id, MIN(transitioned_at) AS p
            FROM lifecycle_transition
            WHERE entity_type = %s AND to_status = 'published'
            GROUP BY entity_id
        )
        SELECT AVG(EXTRACT(EPOCH FROM (p.p - s.s)) / 86400.0) AS avg_days
        FROM pub p JOIN start s USING (entity_id)
        """,
        (entity_type, entity_type),
    )
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


def _fty_pct(conn, entity_type: str) -> Optional[float]:
    """First-time-through yield % for this entity type (no rejected state)."""
    cur = conn.cursor()
    cur.execute(
        """
        WITH pub AS (
            SELECT DISTINCT entity_id FROM lifecycle_transition
            WHERE entity_type = %s AND to_status = 'published'
        ),
        rej AS (
            SELECT DISTINCT entity_id FROM lifecycle_transition
            WHERE entity_type = %s AND to_status = 'rejected'
        )
        SELECT COUNT(*) AS p, COUNT(*) FILTER (WHERE r.entity_id IS NULL) AS ftt
        FROM pub p LEFT JOIN rej r USING (entity_id)
        """,
        (entity_type, entity_type),
    )
    p, ftt = cur.fetchone()
    if not p:
        return None
    return round(ftt / p * 100.0, 2)


def capture_snapshots(
    conn, entity_type: Optional[str] = None, source_ref: str = "process_control",
) -> int:
    """Compute KPI snapshots per entity type and store them."""
    types = [entity_type] if entity_type else _distinct_types(conn)
    cur = conn.cursor()
    n = 0
    for et in types:
        ct = _cycle_time_mean(conn, et)
        fty = _fty_pct(conn, et)
        if ct is not None:
            cur.execute(
                """INSERT INTO process_kpi_snapshot
                     (entity_type, metric, value, source_ref)
                   VALUES (%s, 'cycle_time_days', %s, %s)""",
                (et, ct, source_ref),
            )
            n += 1
        if fty is not None:
            cur.execute(
                """INSERT INTO process_kpi_snapshot
                     (entity_type, metric, value, source_ref)
                   VALUES (%s, 'fty_pct', %s, %s)""",
                (et, fty, source_ref),
            )
            cur.execute(
                """INSERT INTO process_kpi_snapshot
                     (entity_type, metric, value, source_ref)
                   VALUES (%s, 'rework_rate_pct', %s, %s)""",
                (et, round(100.0 - fty, 2), source_ref),
            )
            n += 2
    conn.commit()
    return n


def evaluate_control(
    conn, entity_type: str, metric: str, k: float = 3.0,
) -> Dict[str, Any]:
    """Compute control limits over the KPI series and flag out-of-control points."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT period, value, captured_at FROM process_kpi_snapshot
        WHERE entity_type = %s AND metric = %s
        ORDER BY captured_at
        """,
        (entity_type, metric),
    )
    rows = cur.fetchall()
    values = [float(r["value"]) for r in rows]
    limits = control_limits(values, k)
    points = []
    for r, v in zip(rows, values):
        ooc = (limits["n"] > 0) and (v > limits["ucl"] or v < limits["lcl"])
        points.append(
            {
                "period": r["period"],
                "value": v,
                "captured_at": r["captured_at"],
                "out_of_control": ooc,
            }
        )
    return {
        "entity_type": entity_type,
        "metric": metric,
        "limits": limits,
        "points": points,
        "out_of_control_count": sum(1 for p in points if p["out_of_control"]),
    }


def ctq_report(conn, process: Optional[str] = None) -> List[Dict[str, Any]]:
    """List CTQ definitions with their latest snapshot value (if any)."""
    where = ""
    params: List[Any] = []
    if process:
        where = "WHERE process = %s"
        params.append(process)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        f"""
        SELECT c.process, c.ctq_name, c.target, c.unit, c.upper_spec, c.lower_spec,
               (SELECT value FROM process_kpi_snapshot k
                 WHERE k.entity_type = c.process AND k.metric = c.ctq_name
                 ORDER BY k.captured_at DESC LIMIT 1) AS latest_value
        FROM process_ctq c
        {where}
        ORDER BY c.process, c.ctq_name
        """,
        params,
    )
    return [dict(r) for r in cur.fetchall()]


# --- CLI --------------------------------------------------------------------

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "capture":
            out = {"captured": capture_snapshots(conn, args.entity_type)}
        elif args.command == "chart":
            out = evaluate_control(conn, args.entity_type, args.metric)
        elif args.command == "ctq":
            out = ctq_report(conn, args.process)
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process control / SPC")
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--entity-type", default=None)
    ch = sub.add_parser("chart")
    ch.add_argument("--entity-type", required=True)
    ch.add_argument("--metric", required=True)
    ct = sub.add_parser("ctq")
    ct.add_argument("--process", default=None)
    args = parser.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
