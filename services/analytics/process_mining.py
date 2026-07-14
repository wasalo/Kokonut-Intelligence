"""Process mining over the lifecycle_transition ledger.

Treats the generic lifecycle_transition log (179) as a process event
log and reconstructs, per governed entity type:

  * discovered variants      - the ordered status paths actually taken
  * conformance             - which traces violate the canonical model
  * case timelines          - per-instance step durations
  * cycle-time distribution - draft -> published elapsed time per instance

The canonical model lives in the process_model table (182); classify
uses it so conformance is uniform across every instrumented entity.
Reads only; persist_variants() may cache the discovered set.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db


# --- model loading ----------------------------------------------------------

_MODEL_COLS = "status, is_terminal, allowed_next, is_goal, is_initial"


def load_model(conn, entity_type: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Return {status: {is_terminal, allowed_next[], is_goal, is_initial}}.

    With ``entity_type`` given, per-type rows take precedence over the default
    '*' model (so a table with its own state machine is not polluted by the
    5-state publication vocabulary). With no argument, returns the default '*'
    model only.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    model: Dict[str, Dict[str, Any]] = {}
    if entity_type is not None:
        cur.execute(
            f"SELECT {_MODEL_COLS} FROM process_model WHERE entity_type = %s",
            (entity_type,),
        )
        for r in cur.fetchall():
            model[r["status"]] = _row_to_node(r)
        cur.execute(
            f"SELECT {_MODEL_COLS} FROM process_model WHERE entity_type = '*'"
        )
        for r in cur.fetchall():
            model.setdefault(r["status"], _row_to_node(r))
    else:
        cur.execute(f"SELECT {_MODEL_COLS} FROM process_model WHERE entity_type = '*'")
        for r in cur.fetchall():
            model[r["status"]] = _row_to_node(r)
    return model


def _row_to_node(r) -> Dict[str, Any]:
    return {
        "is_terminal": bool(r["is_terminal"]),
        "allowed_next": list(r["allowed_next"] or []),
        "is_goal": bool(r.get("is_goal")),
        "is_initial": bool(r.get("is_initial")),
    }


def goal_state(model: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """The success terminal state of a model (fallback: first terminal)."""
    for s, n in model.items():
        if n.get("is_goal"):
            return s
    for s, n in model.items():
        if n["is_terminal"]:
            return s
    return None


def initial_state(model: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """The entry state of a model (fallback: 'draft' if present)."""
    for s, n in model.items():
        if n.get("is_initial"):
            return s
    if "draft" in model:
        return "draft"
    for s, n in model.items():
        if not n["is_terminal"]:
            return s
    return None


def fail_state(model: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """A terminal-but-not-goal (failure) state, if any."""
    for s, n in model.items():
        if n["is_terminal"] and not n.get("is_goal"):
            return s
    return None


# --- trace extraction --------------------------------------------------------

def get_traces(
    conn,
    entity_type: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """Group lifecycle_transition rows into ordered traces per (type, id)."""
    sql = """
        SELECT entity_type, entity_id, from_status, to_status, transitioned_at
        FROM lifecycle_transition
    """
    params: List[Any] = []
    if entity_type:
        sql += " WHERE entity_type = %s"
        params.append(entity_type)
    sql += " ORDER BY entity_type, entity_id, transitioned_at"
    if limit:
        sql += " LIMIT %s"
        params.append(int(limit))
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    traces: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for r in cur.fetchall():
        key = (r["entity_type"], str(r["entity_id"]))
        traces.setdefault(key, []).append(
            {
                "from_status": r["from_status"],
                "to_status": r["to_status"],
                "at": r["transitioned_at"],
            }
        )
    return traces


def _sequence(trace: List[Dict[str, Any]]) -> List[str]:
    return [t["to_status"] for t in trace]


# --- conformance -------------------------------------------------------------

def classify_conformance(
    step_sequence: List[str],
    model: Dict[str, Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Return (is_conforming, reasons[]) for a status sequence."""
    reasons: List[str] = []
    seq = list(step_sequence)
    if not seq:
        return False, ["empty trace"]
    # Every status must be known to the model.
    for s in seq:
        if s not in model:
            reasons.append(f"unknown status '{s}'")
    if seq[0] != "draft":
        reasons.append(f"trace does not start at 'draft' (starts at '{seq[0]}')")
    for prev, nxt in zip(seq, seq[1:]):
        node = model.get(prev)
        if not node:
            continue
        if nxt not in node["allowed_next"]:
            reasons.append(f"illegal transition '{prev}' -> '{nxt}'")
        if node["is_terminal"]:
            reasons.append(f"transition out of terminal state '{prev}'")
    # Terminal status must be the final element.
    for i, s in enumerate(seq):
        node = model.get(s)
        if node and node["is_terminal"] and i != len(seq) - 1:
            reasons.append(f"terminal state '{s}' is not the final step")
            break
    return (len(reasons) == 0), reasons


# --- public API --------------------------------------------------------------

def discover_variants(
    conn,
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Aggregate traces into variants with counts + conformance."""
    traces = get_traces(conn, entity_type=entity_type)
    agg: Dict[Tuple[str, str], Dict[str, Any]] = {}
    models: Dict[str, Dict[str, Any]] = {}
    for (etype, _eid), trace in traces.items():
        seq = _sequence(trace)
        sig = ">".join(seq)
        key = (etype, sig)
        if key not in agg:
            models.setdefault(etype, load_model(conn, etype))
            is_conf, reasons = classify_conformance(seq, models[etype])
            agg[key] = {
                "entity_type": etype,
                "variant_signature": sig,
                "step_sequence": seq,
                "instance_count": 0,
                "is_conforming": is_conf,
                "conformance_notes": reasons,
                "last_seen": trace[-1]["at"],
            }
        agg[key]["instance_count"] += 1
        last = trace[-1]["at"]
        if agg[key]["last_seen"] is None or (last and last > agg[key]["last_seen"]):
            agg[key]["last_seen"] = last
    out = list(agg.values())
    out.sort(key=lambda v: (v["entity_type"], -v["instance_count"]))
    return out


def check_conformance(
    conn,
    entity_type: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return only the non-conforming traces with reasons."""
    traces = get_traces(conn, entity_type=entity_type, limit=limit)
    models: Dict[str, Dict[str, Any]] = {}
    findings: List[Dict[str, Any]] = []
    for (etype, eid), trace in traces.items():
        seq = _sequence(trace)
        models.setdefault(etype, load_model(conn, etype))
        is_conf, reasons = classify_conformance(seq, models[etype])
        if not is_conf:
            findings.append(
                {
                    "entity_type": etype,
                    "entity_id": eid,
                    "step_sequence": seq,
                    "reasons": reasons,
                }
            )
    return findings


def case_timeline(
    conn,
    entity_id: str,
) -> List[Dict[str, Any]]:
    """Per-step timeline (with durations) for a single entity instance."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT from_status, to_status, transitioned_at
        FROM lifecycle_transition
        WHERE entity_id = %s::uuid
        ORDER BY transitioned_at
        """,
        (entity_id,),
    )
    rows = cur.fetchall()
    timeline: List[Dict[str, Any]] = []
    prev_at = None
    for r in rows:
        at = r["transitioned_at"]
        duration_s = None
        if prev_at is not None and at is not None:
            duration_s = (at - prev_at).total_seconds()
        timeline.append(
            {
                "from_status": r["from_status"],
                "to_status": r["to_status"],
                "transitioned_at": at,
                "duration_seconds": duration_s,
            }
        )
        prev_at = at
    return timeline


def cycle_time_distribution(
    conn,
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Elapsed days from entry to the model's goal state, per instance."""
    traces = get_traces(conn, entity_type=entity_type)
    models: Dict[str, Dict[str, Any]] = {}
    out: List[Dict[str, Any]] = []
    for (etype, eid), trace in traces.items():
        seq = _sequence(trace)
        models.setdefault(etype, load_model(conn, etype))
        goal = goal_state(models[etype])
        if seq and goal and seq[-1] == goal:
            start = trace[0]["at"]
            end = None
            for t in trace:
                if t["to_status"] == goal:
                    end = t["at"]
                    break
            if start and end:
                days = (end - start).total_seconds() / 86400.0
                out.append(
                    {
                        "entity_type": etype,
                        "entity_id": eid,
                        "cycle_time_days": round(days, 4),
                    }
                )
    return out


def persist_variants(
    conn,
    entity_type: Optional[str] = None,
) -> int:
    """Upsert discovered variants into process_variant for trend tracking."""
    variants = discover_variants(conn, entity_type=entity_type)
    cur = conn.cursor()
    updated = 0
    for v in variants:
        cur.execute(
            """
            INSERT INTO process_variant
                (entity_type, variant_signature, step_sequence,
                 instance_count, is_conforming, conformance_notes, last_seen)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (entity_type, variant_signature) DO UPDATE SET
                instance_count = EXCLUDED.instance_count,
                is_conforming = EXCLUDED.is_conforming,
                conformance_notes = EXCLUDED.conformance_notes,
                last_seen = EXCLUDED.last_seen
            """,
            (
                v["entity_type"],
                v["variant_signature"],
                json.dumps(v["step_sequence"]),
                v["instance_count"],
                v["is_conforming"],
                json.dumps(v["conformance_notes"]),
                v["last_seen"],
            ),
        )
        updated += 1
    conn.commit()
    return updated


# --- CLI --------------------------------------------------------------------

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "discover":
            out = discover_variants(conn, args.entity_type)
        elif args.command == "conformance":
            out = check_conformance(conn, args.entity_type, args.limit)
        elif args.command == "timeline":
            out = case_timeline(conn, args.entity_id)
        elif args.command == "cycle-times":
            out = cycle_time_distribution(conn, args.entity_type)
        elif args.command == "persist":
            n = persist_variants(conn, args.entity_type)
            out = {"persisted_variants": n}
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process mining (lifecycle ledger)")
    parser.add_argument("--entity-type", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("discover", "conformance", "cycle-times", "persist"):
        p = sub.add_parser(name)
        p.add_argument("--entity-type", default=None)
        if name == "conformance":
            p.add_argument("--limit", type=int, default=None)
    tl = sub.add_parser("timeline")
    tl.add_argument("--entity-id", required=True)
    args = parser.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
