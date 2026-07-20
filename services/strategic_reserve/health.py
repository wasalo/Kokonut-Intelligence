"""Strategic Reserve health: adequacy, drawdown headroom, trigger status.

Read-only analytics over the ``strategic_reserve`` registry. Mirrors the
resilience-scoring style of ``services.crisp`` by turning held-vs-target
math and threshold-breach checks into a per-reserve health verdict.

The trigger engine implements the strategic-reserve literature's defining
property: a reserve is released only when a monitored metric breaches its
threshold (the TSO "strategic reserve" analog), never on a schedule.
Release proposals are surfaced for human approval; this module never writes
governed state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row) -> Dict[str, Any]:
    from uuid import UUID

    return {
        k: str(v) if isinstance(v, UUID) else v for k, v in dict(row).items()
    }


def compute_adequacy(reserve: Dict[str, Any]) -> Dict[str, Any]:
    """Held-vs-target adequacy for a single reserve row."""
    held = float(reserve.get("held_quantity") or 0)
    target = float(reserve.get("capacity_target") or 0)
    adequacy_pct = round((held / target) * 100, 2) if target > 0 else None
    headroom = round(target - held, 6) if target > 0 else None
    return {
        "held_quantity": held,
        "capacity_target": target,
        "unit": reserve.get("unit"),
        "adequacy_pct": adequacy_pct,
        "drawdown_headroom": headroom,
        "status": reserve.get("status"),
    }


def _breaches(operator: Optional[str], value: Optional[float], threshold: Optional[float]) -> Optional[bool]:
    """Return whether ``value`` breaches the release threshold.

    None when no trigger is defined or the monitored value is missing.
    """
    if not operator or threshold is None or value is None:
        return None
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "eq":
        return value == threshold
    return None


def _preempt_value(operator: Optional[str], threshold: Optional[float], preempt_pct: Optional[float]) -> Optional[float]:
    """Compute the forward-deployment (preempt) threshold.

    The preempt threshold is ``preempt_pct`` of the distance from a neutral
    baseline (0) to the hard ``threshold``. For a falling-is-bad operator
    (``lt``/``lte``) the baseline is +infinity-ish, so we treat the preempt
    point as ``threshold * preempt_pct`` (i.e. 80% of the way to breach).
    For a rising-is-bad operator (``gt``/``gte``) the same multiplicative rule
    applies from 0. Returns None when not configured.
    """
    if preempt_pct is None or threshold is None or not operator:
        return None
    if operator in ("lt", "lte"):
        # falling is bad: deploy when value drops to preempt_pct of threshold
        return threshold * preempt_pct
    if operator in ("gt", "gte"):
        # rising is bad: deploy when value rises to preempt_pct of threshold
        return threshold * preempt_pct
    return None


def evaluate_trigger(
    conn, reserve: Dict[str, Any]
) -> Dict[str, Any]:
    """Evaluate the release trigger for a reserve against the latest metric.

    Uses the most recent ``metric_value`` row for ``trigger_metric_key``
    (network scope when the reserve scope is network, else the reserve's
    ``scope_id``). Returns whether the breach condition is met, the observed
    value, and the release threshold.

    When the reserve defines ``preempt_threshold_pct`` (>0), the engine also
    surfaces a DRAFT forward-deployment proposal once the observed value enters
    the preempt band (``preempt_pct`` of the way to the hard breach) — the
    "best defense is a good offense" posture. Forward deployment is still DRAFT
    and requires human approval; this module never draws down autonomously.
    """
    key = reserve.get("trigger_metric_key")
    operator = reserve.get("trigger_operator")
    threshold = reserve.get("trigger_threshold")
    if not key:
        return {"trigger_defined": False, "breach": None}

    scope_id = reserve.get("scope_id")
    params: List[Any] = [key]
    scope_filter = ""
    if scope_id:
        scope_filter = " AND mv.location_id = %s"
        params.append(scope_id)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT mv.value AS value, mv.computed_at
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE md.metric_key = %s {scope_filter}
            ORDER BY mv.computed_at DESC
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()

    observed = float(row["value"]) if row and row.get("value") is not None else None
    breach = _breaches(operator, observed, threshold)

    preempt_pct = reserve.get("preempt_threshold_pct")
    preempt_value = _preempt_value(operator, threshold, preempt_pct if preempt_pct else None)
    preempt_breach = _breaches(operator, observed, preempt_value) if preempt_value is not None else None
    # Forward-deployment proposal fires on the preempt band (but not yet hard breach).
    preempt_proposed = bool(preempt_breach) and not bool(breach)

    return {
        "trigger_defined": True,
        "metric_key": key,
        "operator": operator,
        "threshold": threshold,
        "observed_value": observed,
        "breach": breach,
        "release_proposed": bool(breach),
        "preempt_threshold_pct": preempt_pct,
        "preempt_value": preempt_value,
        "preempt_breach": preempt_breach,
        "preempt_proposed": preempt_proposed,
    }


def reserve_health(
    conn, scope: Optional[str] = None, scope_id: Optional[str] = None
) -> Dict[str, Any]:
    """Compute health for all (or scope-filtered) reserves."""
    where = []
    params: List[Any] = []
    if scope:
        where.append("entity_scope = %s")
        params.append(scope)
    if scope_id:
        where.append("scope_id = %s")
        params.append(scope_id)

    sql = "SELECT * FROM strategic_reserve"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY reserve_type, name"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        reserves = [dict(r) for r in cur.fetchall()]

    out = []
    for r in reserves:
        adequacy = compute_adequacy(r)
        trigger = evaluate_trigger(conn, r)
        out.append({
            "reserve_code": r.get("reserve_code"),
            "reserve_type": r.get("reserve_type"),
            "entity_scope": r.get("entity_scope"),
            "name": r.get("name"),
            "adequacy": adequacy,
            "trigger": trigger,
        })
    return {
        "reserve_count": len(out),
        "reserves": out,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def seed_vault_health(conn, location_id: str) -> Dict[str, Any]:
    """Biodiversity / seed-vault proxy for a location (Svalbard/Frozen Ark analog).

    Counts distinct tree species and distinct crop lines held in reserve as
    agro-biodiversity insurance. Read-only; no new source tables.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                (SELECT COUNT(DISTINCT species_name) FROM tree_inventory
                 WHERE location_id = %s) AS distinct_species,
                (SELECT COUNT(DISTINCT crop_id) FROM crop_cycle
                 WHERE location_id = %s) AS distinct_crop_lines
            """,
            (location_id, location_id),
        )
        row = cur.fetchone() or {}
        distinct_species = int(row.get("distinct_species") or 0)
        distinct_crop_lines = int(row.get("distinct_crop_lines") or 0)

    total_lines = distinct_species + distinct_crop_lines
    # A reserve is "adequately diversified" at >= 30 distinct lines (pilot target).
    target = 30
    adequacy_pct = round((total_lines / target) * 100, 2) if target > 0 else None
    return {
        "location_id": location_id,
        "distinct_species": distinct_species,
        "distinct_crop_lines": distinct_crop_lines,
        "distinct_lines_held": total_lines,
        "diversity_target": target,
        "adequacy_pct": adequacy_pct,
        "insurance_status": "adequate" if total_lines >= target else "thin",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
