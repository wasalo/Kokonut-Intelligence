"""Preemptive Intervention Planner — the "best defense is a good offense" layer.

Read-only threatcasting analytics that converts a flag's *warning band* into an
actionable lead time BEFORE the hard critical breach. The planner never writes
governed state and never triggers autonomous action; it returns DRAFT proposals
for human approval.

Lead-time model
---------------
A flag exposes three thresholds: ``threshold_normal``, ``threshold_warning`` and
``threshold_critical`` (with a ``comparison_operator`` that says whether "rising"
is bad, e.g. ``gte`` for rainfall deficit or ``lte`` for soil moisture). The band
between warning and critical is the "reaction margin". The planner estimates how
many check cycles remain before the metric is projected to cross critical:

    cycles_to_critical = ceil(
        (critical_distance / warning_distance) * warning_age_cycles + 1
    )

where distances are measured in the direction the operator moves (so the planner
is symmetric for rising and falling threats). ``lead_time_hours`` is then
``cycles_to_critical * check_frequency_hours``. When the most recent observation
is already past warning but not yet critical, a DRAFT preemptive action is
surfaced with that lead time and a severity scaled to how thin the remaining
margin is.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _operator_rising(operator: Optional[str]) -> bool:
    """Is "higher value" the dangerous direction for this flag?"""
    return operator in ("gte", "gt")


def _jsonb(obj: Any) -> Any:
    import json as _json

    return _json.dumps(obj)


def _distance(value: float, threshold: float, rising: bool) -> float:
    """Signed distance of ``value`` from ``threshold`` in the dangerous direction.

    Positive means already past the threshold (in the bad direction).
    """
    if rising:
        return value - threshold
    return threshold - value


def _flag_status(flag: Dict[str, Any], value: Optional[float]) -> str:
    """Recompute warning/critical/normal status for a flag given a value."""
    if value is None:
        return "unknown"
    rising = _operator_rising(flag.get("comparison_operator"))
    crit = flag.get("threshold_critical")
    warn = flag.get("threshold_warning")
    if crit is not None and _distance(value, crit, rising) >= 0:
        return "critical"
    if warn is not None and _distance(value, warn, rising) >= 0:
        return "warning"
    return "normal"


def _lead_time_hours(
    flag: Dict[str, Any],
    value: float,
    last_checked: Optional[datetime],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Compute projected lead time to critical breach (read-only estimate).

    Returns a dict with ``lead_time_hours``, ``cycles_to_critical`` and the
    fraction of the warning→critical margin already consumed.
    """
    now = now or datetime.now(timezone.utc)
    rising = _operator_rising(flag.get("comparison_operator"))
    warn = flag.get("threshold_warning")
    crit = flag.get("threshold_critical")
    freq = int(flag.get("check_frequency_hours") or 24)

    if warn is None or crit is None:
        return {
            "computable": False,
            "reason": "warning/critical thresholds incomplete",
            "lead_time_hours": None,
            "cycles_to_critical": None,
            "margin_consumed_pct": None,
        }

    warn_dist = _distance(value, warn, rising)
    crit_dist = _distance(value, crit, rising)
    band = abs(crit - warn)
    if band <= 0:
        return {
            "computable": False,
            "reason": "zero warning→critical band",
            "lead_time_hours": None,
            "cycles_to_critical": None,
            "margin_consumed_pct": None,
        }

    margin_consumed_pct = round(min(max(warn_dist / band, 0.0), 1.0) * 100, 2)

    # How many check cycles until we expect to reach critical?
    # If already past warning, project at least one more cycle; scale linearly
    # by how far into the band we already are (conservative lower bound).
    if warn_dist <= 0:
        cycles_to_critical = 1
    else:
        cycles_to_critical = max(1, math.ceil(crit_dist / warn_dist) if warn_dist else 1)

    # If we know when the value was last checked, add elapsed cycles since.
    elapsed_cycles = 0
    if last_checked is not None:
        try:
            delta = (now - last_checked).total_seconds() / 3600.0
            elapsed_cycles = max(0, int(delta // freq))
        except TypeError:
            elapsed_cycles = 0

    lead_cycles = max(0, cycles_to_critical - elapsed_cycles)
    return {
        "computable": True,
        "lead_time_hours": lead_cycles * freq,
        "cycles_to_critical": lead_cycles,
        "margin_consumed_pct": margin_consumed_pct,
        "check_frequency_hours": freq,
    }


def plan_preemptive_actions(
    conn, location_id: Optional[str] = None
) -> Dict[str, Any]:
    """Build DRAFT preemptive intervention proposals for warning-band flags.

    Read-only: queries ``threat_flag`` + latest flagged observation and returns
    proposals. No governed rows are written; the caller (CLI / report) decides
    whether to surface them for human approval.
    """
    sql = """
        SELECT tf.id, tf.threat_id, tf.flag_name, tf.indicator_type,
               tf.threshold_critical, tf.threshold_warning, tf.threshold_normal,
               tf.comparison_operator, tf.unit, tf.data_source,
               tf.check_frequency_hours, tf.last_checked_at, tf.last_value,
               t.name AS threat_name, t.type AS threat_type,
               t.severity AS threat_severity, t.probability AS threat_probability
        FROM threat_flag tf
        JOIN threat t ON t.id = tf.threat_id
        WHERE tf.status <> 'critical'
    """
    params: List[Any] = []
    if location_id:
        sql += " AND t.location_id = %s"
        params.append(location_id)
    sql += " ORDER BY t.location_id, tf.threat_id, tf.flag_name"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        flags = [dict(r) for r in cur.fetchall()]

    proposals: List[Dict[str, Any]] = []
    for flag in flags:
        value = flag.get("last_value")
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        status = _flag_status(flag, value)
        if status != "warning":
            continue

        last_checked = flag.get("last_checked_at")
        lt = _lead_time_hours(flag, value, last_checked)
        if not lt.get("computable"):
            continue

        margin = float(lt.get("margin_consumed_pct") or 0)
        # Severity scales with how thin the remaining margin is.
        if margin >= 75:
            severity = "high"
        elif margin >= 40:
            severity = "medium"
        else:
            severity = "low"

        lead = int(lt.get("lead_time_hours") or 0)
        proposals.append({
            "status": "draft",
            "threat_id": str(flag.get("threat_id")),
            "threat_name": flag.get("threat_name"),
            "threat_type": flag.get("threat_type"),
            "threat_severity": flag.get("threat_severity"),
            "threat_probability": flag.get("threat_probability"),
            "flag_id": str(flag.get("id")),
            "flag_name": flag.get("flag_name"),
            "indicator_type": flag.get("indicator_type"),
            "observed_value": value,
            "unit": flag.get("unit"),
            "lead_time_hours": lead,
            "margin_consumed_pct": margin,
            "severity": severity,
            "action": (
                f"Preemptive intervention window open for '{flag.get('flag_name')}' "
                f"on threat '{flag.get('threat_name')}': ~{lead}h until projected "
                f"critical breach (margin {margin:.0f}% consumed). Recommend "
                f"intervention before breach."
            ),
            "requires_human_approval": True,
        })

    proposals.sort(key=lambda p: (p["lead_time_hours"], -p["margin_consumed_pct"]))

    # Discovered double-check: a warning flag may, by cross-impact relation,
    # reveal a second latent threat (the "discovered attack" / double-check
    # tactic). Reusing threat_cross_impact keeps this read-only and avoids a
    # new table.
    double_checks = []
    for flag in flags:
        value = flag.get("last_value")
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if _flag_status(flag, value) != "warning":
            continue
        companions = _find_companion_threats(conn, flag.get("threat_id"))
        for comp in companions:
            double_checks.append({
                "status": "draft",
                "flag_id": str(flag.get("id")),
                "flag_name": flag.get("flag_name"),
                "source_threat_id": str(flag.get("threat_id")),
                "source_threat_name": flag.get("threat_name"),
                "companion_threat_id": str(comp.get("target_threat_id")),
                "companion_threat_name": comp.get("target_threat_name"),
                "impact_type": comp.get("impact_type"),
                "impact_magnitude": comp.get("impact_magnitude"),
                "action": (
                    f"'{flag.get('flag_name')}' warning on '{flag.get('threat_name')}' "
                    f"also reveals latent threat '{comp.get('target_threat_name')}' "
                    f"({comp.get('impact_type')}). Treat as a discovered double-check: "
                    f"intervene on the source to defuse both."
                ),
                "requires_human_approval": True,
            })

    double_checks.sort(key=lambda d: (d["impact_magnitude"] or 0), reverse=True)
    return {
        "location_id": location_id,
        "proposal_count": len(proposals),
        "proposals": proposals,
        "double_check_count": len(double_checks),
        "double_checks": double_checks,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "All proposals are DRAFT and require human approval. This planner "
            "performs no autonomous action and writes no governed state."
        ),
    }


def _find_companion_threats(conn, threat_id: Optional[str]) -> List[Dict[str, Any]]:
    """Return enabled cross-impact relations that reveal a latent threat.

    Mirrors the "discovered attack" tactic: moving one piece (a warning flag)
    unmasks a second threat. Only 'amplifies'/'triggers' relations are treated
    as revealing a genuine second threat.
    """
    if not threat_id:
        return []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT ci.target_threat_id, ci.impact_type, ci.impact_magnitude,
                   t.threat_name AS target_threat_name
            FROM threat_cross_impact ci
            JOIN threat t ON t.id = ci.target_threat_id
            WHERE ci.source_threat_id = %s
              AND ci.is_enabled = TRUE
              AND ci.impact_type IN ('amplifies', 'triggers')
            ORDER BY ci.impact_magnitude DESC NULLS LAST
            """,
            (threat_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def propose_double_checks(
    conn, location_id: Optional[str] = None, actor: Optional[str] = None
) -> Dict[str, Any]:
    """Write DRAFT tactical_opportunity rows for discovered double-checks.

    Status is forced to 'draft' in code; no autonomous action or publish.
    """
    plan = plan_preemptive_actions(conn, location_id=location_id)
    created = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for dc in plan.get("double_checks", []):
            opp_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO tactical_opportunity
                    (id, opportunity_type, location_id, severity,
                     opportunity_summary, source_refs, status, proposed_by)
                VALUES (%s, 'double_check', %s, %s, %s, %s, 'draft', %s)
                RETURNING *
                """,
                (
                    opp_id,
                    location_id,
                    "high" if (dc.get("impact_magnitude") or 0) >= 0.5 else "medium",
                    dc["action"],
                    _jsonb({
                        "flag_id": dc["flag_id"],
                        "source_threat_id": dc["source_threat_id"],
                        "companion_threat_id": dc["companion_threat_id"],
                        "impact_type": dc["impact_type"],
                    }),
                    actor,
                ),
            )
            created.append(dict(cur.fetchone()))
    conn.commit()
    return {
        "location_id": location_id,
        "proposed_count": len(created),
        "opportunities": created,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "DRAFT opportunities created; human review required to act.",
    }
