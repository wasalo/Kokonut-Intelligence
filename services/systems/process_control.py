"""Statistical process control over process KPIs (BPM Optimize phase).

Computes control limits on process KPIs (cycle time, first-time-through
yield, rework rate) derived from the lifecycle ledger, detects
out-of-control points, and reports CTQ conformance. Pairs with
process_mining (variant/cycle-time source) and value_stream (FTY source).

Reads lifecycle_transition; writes process_kpi_snapshot when capturing.
"""

from __future__ import annotations

import argparse
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from services.common.database import get_db
from services.common.cli import print_json

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


def compute_cp_cpk(
    values: List[float],
    usl: float,
    lsl: float,
) -> Dict[str, float]:
    """Compute process capability indices Cp and Cpk.

    Cp  = (USL - LSL) / (6 * sigma)   -- potential capability
    Cpk = min((USL - mean) / (3 * sigma), (mean - LSL) / (3 * sigma)) -- actual capability

    A Cpk < 1.0 indicates the process is not capable.
    A Cpk between 1.0 and 1.33 indicates marginal capability.
    A Cpk >= 1.33 indicates the process is capable.
    A Cpk >= 1.67 indicates the process is highly capable.
    """
    n = len(values)
    if n < 2 or usl <= lsl:
        return {"n": n, "cp": None, "cpk": None, "sigma": None,
                "mean": None, "capable": None, "rating": "insufficient_data"}

    mean = statistics.fmean(values)
    sigma = statistics.stdev(values)

    if sigma == 0:
        return {"n": n, "cp": float("inf"), "cpk": float("inf"),
                "sigma": 0.0, "mean": round(mean, 6),
                "capable": True, "rating": "perfect"}

    cp = (usl - lsl) / (6 * sigma)
    cpk_upper = (usl - mean) / (3 * sigma)
    cpk_lower = (mean - lsl) / (3 * sigma)
    cpk = min(cpk_upper, cpk_lower)

    if cpk >= 1.67:
        rating = "highly_capable"
    elif cpk >= 1.33:
        rating = "capable"
    elif cpk >= 1.0:
        rating = "marginal"
    else:
        rating = "not_capable"

    return {
        "n": n,
        "cp": round(cp, 4),
        "cpk": round(cpk, 4),
        "cpk_upper": round(cpk_upper, 4),
        "cpk_lower": round(cpk_lower, 4),
        "sigma": round(sigma, 6),
        "mean": round(mean, 6),
        "usl": usl,
        "lsl": lsl,
        "capable": cpk >= 1.0,
        "rating": rating,
    }


def ctq_capability(
    conn,
    entity_type: str,
    metric: str,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute Cp/Cpk for a CTQ metric using spec limits from process_ctq or arguments."""
    if usl is None or lsl is None:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT upper_spec, lower_spec FROM process_ctq WHERE process = %s AND ctq_name = %s",
            (entity_type, metric),
        )
        row = cur.fetchone()
        if row:
            if usl is None:
                usl = float(row["upper_spec"]) if row["upper_spec"] is not None else None
            if lsl is None:
                lsl = float(row["lower_spec"]) if row["lower_spec"] is not None else None

    if usl is None or lsl is None:
        return {"error": "No spec limits provided or found in process_ctq"}

    cur = conn.cursor()
    cur.execute(
        "SELECT value FROM process_kpi_snapshot WHERE entity_type = %s AND metric = %s ORDER BY captured_at",
        (entity_type, metric),
    )
    values = [float(r[0]) for r in cur.fetchall()]
    return compute_cp_cpk(values, usl, lsl)


def process_capability(
    conn,
    entity_type: str,
    metric: str,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute Cp, Cpk, Pp, Ppk for a process metric.

    Cp  = (USL - LSL) / (6 * sigma_within)   -- potential capability
    Cpk = min((USL - mean)/(3*sigma_within), (mean-LSL)/(3*sigma_within))
    Pp  = (USL - LSL) / (6 * sigma_overall)  -- process performance
    Ppk = min((USL - mean)/(3*sigma_overall), (mean-LSL)/(3*sigma_overall))

    sigma_within uses short-term estimate (R-bar/d2 or s-bar/c4).
    sigma_overall uses total sample stdev.
    """
    if usl is None or lsl is None:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT upper_spec, lower_spec FROM process_ctq WHERE process = %s AND ctq_name = %s",
            (entity_type, metric),
        )
        row = cur.fetchone()
        if row:
            if usl is None:
                usl = float(row["upper_spec"]) if row["upper_spec"] is not None else None
            if lsl is None:
                lsl = float(row["lower_spec"]) if row["lower_spec"] is not None else None

    if usl is None or lsl is None:
        return {"error": "No spec limits provided or found in process_ctq"}
    if usl <= lsl:
        return {"error": "USL must be greater than LSL"}

    cur = conn.cursor()
    cur.execute(
        "SELECT value FROM process_kpi_snapshot WHERE entity_type = %s AND metric = %s ORDER BY captured_at",
        (entity_type, metric),
    )
    values = [float(r[0]) for r in cur.fetchall()]
    n = len(values)

    if n < 2:
        return {"n": n, "error": "insufficient data"}

    mean = statistics.fmean(values)
    sigma_overall = statistics.stdev(values)

    # Short-term sigma estimate using moving range
    mr = [abs(values[i] - values[i - 1]) for i in range(1, n)]
    mr_bar = statistics.fmean(mr) if mr else 0
    d2 = 1.128  # for subgroup size 2 (individual observations)
    sigma_within = mr_bar / d2 if d2 > 0 else sigma_overall

    if sigma_within == 0:
        sigma_within = sigma_overall if sigma_overall > 0 else 0.0001

    cp = (usl - lsl) / (6 * sigma_within) if sigma_within > 0 else float("inf")
    cpk_u = (usl - mean) / (3 * sigma_within) if sigma_within > 0 else float("inf")
    cpk_l = (mean - lsl) / (3 * sigma_within) if sigma_within > 0 else float("inf")
    cpk = min(cpk_u, cpk_l)

    pp = (usl - lsl) / (6 * sigma_overall) if sigma_overall > 0 else float("inf")
    ppk_u = (usl - mean) / (3 * sigma_overall) if sigma_overall > 0 else float("inf")
    ppk_l = (mean - lsl) / (3 * sigma_overall) if sigma_overall > 0 else float("inf")
    ppk = min(ppk_u, ppk_l)

    sigma_level = round(cpk * 3, 2) if cpk != float("inf") else None

    return {
        "n": n,
        "cp": round(cp, 4),
        "cpk": round(cpk, 4),
        "pp": round(pp, 4),
        "ppk": round(ppk, 4),
        "sigma_within": round(sigma_within, 6),
        "sigma_overall": round(sigma_overall, 6),
        "sigma_level": sigma_level,
        "mean": round(mean, 6),
        "usl": usl,
        "lsl": lsl,
        "capable": cpk >= 1.0,
    }


def persist_capability(
    conn,
    entity_type: str,
    metric: str,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    period: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute and persist capability indices to process_capability table."""
    caps = process_capability(conn, entity_type, metric, usl, lsl)
    if "error" in caps:
        return caps

    sql = """
        INSERT INTO process_capability
            (entity_type, metric, cp, cpk, pp, ppk, sigma_level, period)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (
            entity_type, metric,
            caps["cp"], caps["cpk"], caps["pp"], caps["ppk"],
            caps["sigma_level"], period,
        ))
        conn.commit()
        return {
            "persisted": True,
            "capability": caps,
            "record": _row_to_dict(cur.fetchone()),
        }


def capability_report(
    conn,
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Full capability report across all CTQs."""
    sql = """
        SELECT DISTINCT c.process, c.ctq_name, c.upper_spec, c.lower_spec
        FROM process_ctq c
    """
    params: list = []
    if entity_type:
        sql += " WHERE c.process = %s"
        params.append(entity_type)
    sql += " ORDER BY c.process, c.ctq_name"

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    ctqs = cur.fetchall()

    report = []
    for ctq in ctqs:
        proc = ctq["process"]
        ctq_name = ctq["ctq_name"]
        usl = float(ctq["upper_spec"]) if ctq["upper_spec"] is not None else None
        lsl = float(ctq["lower_spec"]) if ctq["lower_spec"] is not None else None
        caps = process_capability(conn, proc, ctq_name, usl, lsl)
        report.append({
            "entity_type": proc,
            "metric": ctq_name,
            "capability": caps,
        })

    return report


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
        print_json(out)
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
