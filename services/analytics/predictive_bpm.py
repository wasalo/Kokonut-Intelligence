"""Predictive BPM over the lifecycle ledger.

Given an in-flight governed entity, predicts remaining time to `published`
and the probability of breaching an SLA target. Models are empirical:
historical remaining-time distributions per current state, trained from
lifecycle_transition (179). Reuses process_mining.get_traces for the log.

Reads lifecycle_transition; persist_forecasts() may cache predictions.
"""

from __future__ import annotations

import argparse
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from services.common.database import get_db
from services.analytics.process_mining import get_traces, load_model, goal_state
from services.common.cli import print_json

MODEL_VERSION = "v2026.07"


def _median(xs: List[float]) -> float:
    return statistics.median(xs) if xs else 0.0


def compute_state_durations(
    conn, entity_type: Optional[str] = None
) -> Tuple[Dict[str, List[float]], List[float]]:
    """Return (per-state remaining-hours-to-goal, all total-hours-to-goal).

    The "goal" is the model's success terminal state, so this works for any
    entity type (5-state publication, work_item done, market_order delivered,
    metric_value verified, ...).
    """
    traces = get_traces(conn, entity_type=entity_type)
    models: Dict[str, Dict[str, Any]] = {}
    per_state: Dict[str, List[float]] = {}
    totals: List[float] = []
    for _etype, _eid, trace in _iter_traces(traces):
        models.setdefault(_etype, load_model(conn, _etype))
        goal = goal_state(models[_etype])
        seq = [t["to_status"] for t in trace]
        if not seq or not goal or seq[-1] != goal:
            continue
        start = trace[0]["at"]
        end = next(t["at"] for t in trace if t["to_status"] == goal)
        if start and end:
            totals.append((end - start).total_seconds() / 3600.0)
        pub_at = end
        for t in trace:
            terminal = models[_etype].get(t["to_status"], {}).get("is_terminal")
            if terminal:
                continue
            if t["at"] and pub_at:
                rem = (pub_at - t["at"]).total_seconds() / 3600.0
                per_state.setdefault(t["to_status"], []).append(rem)
    return per_state, totals


def _iter_traces(traces):
    for (etype, eid), trace in traces.items():
        yield etype, eid, trace


def predict_remaining(conn, entity_type: str, current_state: str) -> float:
    """Median historical remaining hours from current_state to published."""
    per_state, _ = compute_state_durations(conn, entity_type)
    if current_state in per_state and per_state[current_state]:
        return _median(per_state[current_state])
    # fallback: overall median across all states
    all_rem = [v for vs in per_state.values() for v in vs]
    return _median(all_rem)


def predict(
    conn,
    entity_type: str,
    current_state: str,
    age_hours: float = 0.0,
    sla_target_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """Predict remaining time and SLA-breach probability for one case."""
    per_state, totals = compute_state_durations(conn, entity_type)
    remaining = predict_remaining(conn, entity_type, current_state)
    predicted_total = age_hours + remaining
    breach_prob = None
    if sla_target_hours is not None and totals:
        breach_prob = sum(1 for t in totals if t > sla_target_hours) / len(totals)
    return {
        "entity_type": entity_type,
        "current_state": current_state,
        "age_hours": age_hours,
        "predicted_remaining_hours": round(remaining, 3),
        "predicted_total_hours": round(predicted_total, 3),
        "breach_probability": round(breach_prob, 4) if breach_prob is not None else None,
        "sla_target_hours": sla_target_hours,
        "model_version": MODEL_VERSION,
    }


def current_state_of(conn, entity_type: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Map of in-flight (entity_id -> current_state, age_hours, last_at).

    An instance is in-flight if its latest transition is not a terminal state
    of its entity type's model (per-type aware).
    """
    where = ""
    params: List[Any] = []
    if entity_type:
        where = "AND lt.entity_type = %s"
        params.append(entity_type)
    sql = f"""
        SELECT lt.entity_type, lt.entity_id, lt.to_status, lt.transitioned_at
        FROM lifecycle_transition lt
        JOIN (
            SELECT entity_type, entity_id, MAX(transitioned_at) AS last_at
            FROM lifecycle_transition
            GROUP BY entity_type, entity_id
        ) m USING (entity_type, entity_id)
        WHERE lt.transitioned_at = m.last_at
          {where}
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    distinct = {r["entity_type"] for r in rows}
    term_map: Dict[str, set] = {}
    for et in distinct:
        term_map[et] = {s for s, n in load_model(conn, et).items() if n["is_terminal"]}
    default_term = {s for s, n in load_model(conn).items() if n["is_terminal"]}
    out: Dict[str, Dict[str, Any]] = {}
    now = datetime.now(timezone.utc)
    for r in rows:
        et = r["entity_type"]
        if r["to_status"] in term_map.get(et, default_term):
            continue
        age = (now - r["transitioned_at"]).total_seconds() / 3600.0 if r["transitioned_at"] else 0.0
        out[str(r["entity_id"])] = {
            "entity_type": et,
            "current_state": r["to_status"],
            "age_hours": age,
        }
    return out


def breaches(
    conn,
    entity_type: str,
    sla_target_hours: float,
    threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """In-flight instances whose predicted SLA-breach probability >= threshold."""
    inflight = current_state_of(conn, entity_type)
    results: List[Dict[str, Any]] = []
    for eid, info in inflight.items():
        p = predict(
            conn, entity_type, info["current_state"],
            age_hours=info["age_hours"], sla_target_hours=sla_target_hours,
        )
        if p["breach_probability"] is not None and p["breach_probability"] >= threshold:
            row = dict(p)
            row["entity_id"] = eid
            results.append(row)
    results.sort(key=lambda r: r["breach_probability"] or 0, reverse=True)
    return results


def persist_forecasts(
    conn, entity_type: str, sla_target_hours: Optional[float] = None,
) -> int:
    """Store current in-flight breach predictions into predictive_process_forecast.

    Idempotent per entity: a periodic sweep refreshes the single current
    forecast row for each in-flight instance rather than appending duplicates.
    """
    inflight = current_state_of(conn, entity_type)
    cur = conn.cursor()
    if inflight:
        cur.execute(
            "DELETE FROM predictive_process_forecast WHERE entity_type = %s "
            "AND entity_id::text = ANY(%s)",
            (entity_type, [str(k) for k in inflight.keys()]),
        )
    n = 0
    for eid, info in inflight.items():
        p = predict(
            conn, entity_type, info["current_state"],
            age_hours=info["age_hours"], sla_target_hours=sla_target_hours,
        )
        cur.execute(
            """
            INSERT INTO predictive_process_forecast
                (entity_type, entity_id, current_state, age_hours,
                 predicted_remaining_hours, breach_probability,
                 sla_target_hours, model_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entity_type, eid, p["current_state"], p["age_hours"],
                p["predicted_remaining_hours"], p["breach_probability"],
                sla_target_hours, MODEL_VERSION,
            ),
        )
        n += 1
    conn.commit()
    return n


# --- CLI --------------------------------------------------------------------

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "predict":
            out = predict(conn, args.entity_type, args.state,
                          age_hours=args.age_hours,
                          sla_target_hours=args.sla_target_hours)
        elif args.command == "breaches":
            out = breaches(conn, args.entity_type, args.sla_target_hours,
                           threshold=args.threshold)
        elif args.command == "persist":
            out = {"persisted": persist_forecasts(
                conn, args.entity_type, args.sla_target_hours)}
        else:
            out = {}
        print_json(out)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Predictive BPM (process outcomes)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--entity-type", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--age-hours", type=float, default=0.0)
    p.add_argument("--sla-target-hours", type=float, default=None)
    b = sub.add_parser("breaches")
    b.add_argument("--entity-type", required=True)
    b.add_argument("--sla-target-hours", type=float, required=True)
    b.add_argument("--threshold", type=float, default=0.5)
    pe = sub.add_parser("persist")
    pe.add_argument("--entity-type", required=True)
    pe.add_argument("--sla-target-hours", type=float, default=None)
    args = parser.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
