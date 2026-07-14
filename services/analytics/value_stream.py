"""Value-stream analytics for the data -> governance -> publication pipeline.

Implements the VSM current-state view: work-in-process by stage (excess
inventory waste), draft->published lead time, first-time-through yield
(defect waste), and bottleneck ranking (constraint identification). Reads
the generic lifecycle_transition ledger plus live status columns; never
writes. All table/column identifiers below are constants, not user input.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db

# (table, lifecycle_column) for the governed publication pipeline (5-state
# vocabulary). Most tables carry a location_id (enabling per-location scoping);
# agent_task does not, so it is excluded from location-scoped queries.
_PIPELINE = [
    ("data_stream_post", "status"),
    ("ai_summary", "status"),
    ("impact_claim", "status"),
    ("report_snapshot", "status"),
    ("stakeholder_feedback", "status"),
    ("farm_activity", "status"),
    ("harvest_event", "status"),
    ("agent_task", "review_status"),
]

# All entity types mined/monitored (includes metric_value, which has no status
# column but is tracked via the verified boolean -> draft/verified mapping).
INSTRUMENTED_TYPES = [t for t, _ in _PIPELINE] + ["metric_value"]

_NO_LOCATION = {"agent_task", "ai_summary"}

# VSM value classification of each lifecycle stage.
STAGES = {
    "draft": {"class": "NNVA", "note": "necessary non-value-adding; awaiting action"},
    "submitted": {"class": "NNVA", "note": "awaiting human review"},
    "verified": {"class": "NNVA", "note": "awaiting publication governance"},
    "published": {"class": "VA", "note": "value delivered to customer/published face"},
    "rejected": {"class": "NVA", "note": "waste; requires rework"},
}


def _entity_loc_sql(loc: Optional[str]):
    legs = []
    for tbl, _ in _PIPELINE:
        loc_expr = "NULL::uuid AS location_id" if tbl in _NO_LOCATION else "location_id"
        leg = f"SELECT '{tbl}' AS et, id, {loc_expr} FROM {tbl}"
        if loc:
            if tbl in _NO_LOCATION:
                leg += " WHERE 1 = 0"  # no location dimension; exclude when scoping
            else:
                leg += " WHERE location_id = %(loc)s"
        legs.append(leg)
    return " UNION ALL ".join(legs), ({"loc": loc} if loc else {})


def wip_by_stage(conn, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Current work-in-process counts per stage across the pipeline."""
    legs, params = [], []
    for tbl, col in _PIPELINE:
        leg = f"SELECT '{tbl}' AS entity_type, {col}::text AS status, COUNT(*) AS wip FROM {tbl}"
        if location_id and tbl not in _NO_LOCATION:
            leg += " WHERE location_id = %s"
            params.append(location_id)
        elif location_id and tbl in _NO_LOCATION:
            leg += " WHERE 1 = 0"
        leg += f" GROUP BY {col}::text"
        legs.append(leg)
    sql = " UNION ALL ".join(legs) + " ORDER BY entity_type, wip DESC"
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def stage_lead_times(
    conn, location_id: Optional[str] = None,
    period_start: Optional[str] = None, period_end: Optional[str] = None,
    initial_status: str = "draft", goal_status: str = "published",
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Average entry->goal lead time (days) per entity type.

    ``initial_status``/``goal_status`` let callers drive this for any model
    (e.g. work_item draft->done, market_order pending->delivered).
    """
    ps = period_start or "1970-01-01"
    pe = period_end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    el_sql, el_params = _entity_loc_sql(location_id)
    params: Dict[str, Any] = dict(el_params)
    params.update(ps=ps, pe=pe, goal=goal_status, initial=initial_status)
    et_filter = ""
    if entity_type:
        et_filter = " AND lt.entity_type = %(etype)s"
        params["etype"] = entity_type
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"""
        WITH entity_loc AS ({el_sql}),
        pub AS (
            SELECT lt.entity_type, lt.entity_id, MIN(lt.transitioned_at) AS published_at
            FROM lifecycle_transition lt
            JOIN entity_loc el ON el.et = lt.entity_type AND el.id = lt.entity_id
            WHERE lt.to_status = %(goal)s
              AND lt.transitioned_at >= %(ps)s AND lt.transitioned_at <= %(pe)s
              {et_filter}
            GROUP BY lt.entity_type, lt.entity_id
        ),
        start AS (
            SELECT entity_type, entity_id, MIN(transitioned_at) AS start_at
            FROM lifecycle_transition lt
            WHERE (from_status = %(initial)s OR to_status = %(initial)s)
              {et_filter}
            GROUP BY entity_type, entity_id
        )
        SELECT p.entity_type,
               ROUND(AVG(EXTRACT(EPOCH FROM (p.published_at - s.start_at)) / 86400.0)::numeric, 4) AS avg_lead_days,
               COUNT(*) AS published_count
        FROM pub p
        JOIN start s USING (entity_type, entity_id)
        GROUP BY p.entity_type
        ORDER BY avg_lead_days DESC
    """, params)
    return [dict(r) for r in cur.fetchall()]


def first_time_through(
    conn, location_id: Optional[str] = None,
    period_start: Optional[str] = None, period_end: Optional[str] = None,
    goal_status: str = "published", fail_status: str = "rejected",
    entity_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Share of goal-reaching entities that never entered a failure terminal."""
    ps = period_start or "1970-01-01"
    pe = period_end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    el_sql, el_params = _entity_loc_sql(location_id)
    params: Dict[str, Any] = dict(el_params)
    params.update(ps=ps, pe=pe, goal=goal_status, fail=fail_status)
    et_filter = ""
    if entity_type:
        et_filter = " AND lt.entity_type = %(etype)s"
        params["etype"] = entity_type
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"""
        WITH entity_loc AS ({el_sql}),
        pub AS (
            SELECT DISTINCT lt.entity_type, lt.entity_id
            FROM lifecycle_transition lt
            JOIN entity_loc el ON el.et = lt.entity_type AND el.id = lt.entity_id
            WHERE lt.to_status = %(goal)s
              AND lt.transitioned_at >= %(ps)s AND lt.transitioned_at <= %(pe)s
              {et_filter}
        ),
        rej AS (SELECT DISTINCT entity_type, entity_id FROM lifecycle_transition lt WHERE to_status = %(fail)s {et_filter})
        SELECT COUNT(*) AS published_count,
               COUNT(*) FILTER (WHERE r.entity_type IS NULL) AS first_time_through
        FROM pub p
        LEFT JOIN rej r USING (entity_type, entity_id)
    """, params)
    row = cur.fetchone() or {"published_count": 0, "first_time_through": 0}
    total = int(row.get("published_count") or 0)
    fty = int(row.get("first_time_through") or 0)
    pct = round(fty / total * 100.0, 2) if total > 0 else None
    return {"published_count": total, "first_time_through": fty, "pct": pct}


def bottleneck_ranking(
    conn, location_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Rank entity types by current WIP (the constraint carries the most)."""
    wip = wip_by_stage(conn, location_id)
    by_type: Dict[str, int] = {}
    for r in wip:
        by_type[r["entity_type"]] = by_type.get(r["entity_type"], 0) + int(r["wip"])
    total = sum(by_type.values()) or 1
    ranked = [
        {"entity_type": t, "wip": w, "pct_of_total": round(w / total * 100.0, 2)}
        for t, w in sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return ranked


def current_state_map(
    conn, location_id: Optional[str] = None,
    period_start: Optional[str] = None, period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the VSM current-state map for the pipeline."""
    return {
        "scope": {
            "location_id": location_id,
            "period_start": period_start,
            "period_end": period_end,
        },
        "stages": STAGES,
        "wip_by_stage": wip_by_stage(conn, location_id),
        "stage_lead_times_days": stage_lead_times(conn, location_id, period_start, period_end),
        "first_time_through_yield": first_time_through(conn, location_id, period_start, period_end),
        "bottleneck_ranking": bottleneck_ranking(conn, location_id),
    }


def generate_value_stream_map(
    conn, location_id: Optional[str] = None,
    period_start: Optional[str] = None, period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Report-generator compatible entry point (returns the current-state map)."""
    return current_state_map(conn, location_id, period_start, period_end)


def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "current-state":
            out = current_state_map(conn, args.location_id, args.period_start, args.period_end)
        elif args.command == "wip":
            out = wip_by_stage(conn, args.location_id)
        elif args.command == "lead-times":
            out = stage_lead_times(conn, args.location_id, args.period_start, args.period_end)
        elif args.command == "fty":
            out = first_time_through(conn, args.location_id, args.period_start, args.period_end)
        elif args.command == "bottleneck":
            out = bottleneck_ranking(conn, args.location_id)
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Value-stream analytics (VSM)")
    parser.add_argument("--location-id", default=None)
    parser.add_argument("--period-start", default=None)
    parser.add_argument("--period-end", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("current-state", "wip", "lead-times", "fty", "bottleneck"):
        p = sub.add_parser(name)
        if name in ("current-state", "lead-times", "fty"):
            p.add_argument("--period-start", default=None)
            p.add_argument("--period-end", default=None)
        p.add_argument("--location-id", default=None)
    args = parser.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
