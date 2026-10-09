"""Contribution, benefit, risk, learning, and coordination accounting.

This module records non-equity coordination evidence. Values are observations
with units and methodology; they never mint ownership, alter balances, or
change reputation.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

import psycopg2.extras

from services.analytics.coordination import _conn, _row, add_contribution, add_knowledge_exchange


def record_contribution(*args, **kwargs) -> Dict[str, Any]:
    """Record a proposed contribution without converting it into ownership."""
    return add_contribution(*args, **kwargs)


def assess_contribution_balance(alliance_id: str) -> Dict[str, Any]:
    """Flag materially unequal delivered contributions without assigning reputation."""
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT cp.party_id, COALESCE(SUM(cc.committed_value), 0) AS value,
                      COUNT(*) AS record_count
               FROM coordination_participant cp
               LEFT JOIN coordination_contribution cc
                 ON cc.participant_id = cp.id AND cc.status = 'delivered'
               WHERE cp.alliance_id = %s::uuid AND cp.status IN ('active', 'paused', 'exited')
               GROUP BY cp.party_id
               ORDER BY value DESC""",
            (alliance_id,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    values = [float(row["value"]) for row in rows]
    positive = [value for value in values if value > 0]
    ratio = (max(positive) / min(positive)) if positive and min(positive) else None
    warning = bool(ratio is not None and ratio > 2) or any(value == 0 for value in values)
    return {
        "alliance_id": alliance_id,
        "warning": warning,
        "ratio": round(ratio, 4) if ratio is not None else None,
        "threshold": 2.0,
        "participants": rows,
        "interpretation": "This is a review warning about contribution balance, not a reputation or ownership score.",
    }


def record_partner_event(
    alliance_id: str,
    event_type: str,
    description: str,
    *,
    participant_id: Optional[str] = None,
    severity: Optional[str] = None,
    created_by_party_id: Optional[str] = None,
) -> Dict[str, Any]:
    if event_type not in {"failure", "recovery", "substitution"}:
        raise ValueError("invalid partner event type")
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO coordination_partner_event
               (alliance_id, participant_id, event_type, description, severity, created_by_party_id)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::uuid) RETURNING *""",
            (alliance_id, participant_id, event_type, description, severity, created_by_party_id),
        )
        row = cur.fetchone()
        conn.commit()
        return _row(row) or {}


def record_market_performance(
    alliance_id: str,
    outcome: str,
    notes: str,
    *,
    market_order_id: Optional[str] = None,
    performance_value: Optional[float] = None,
    performance_unit: Optional[str] = None,
    observed_by_party_id: Optional[str] = None,
) -> Dict[str, Any]:
    if outcome not in {"on_time", "late", "fulfilled", "disputed", "cancelled"}:
        raise ValueError("invalid market outcome")
    if not notes.strip():
        raise ValueError("market performance notes are required")
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO coordination_market_observation
               (alliance_id, market_order_id, outcome, performance_value, performance_unit,
                notes, observed_by_party_id)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::uuid) RETURNING *""",
            (alliance_id, market_order_id, outcome, performance_value, performance_unit, notes, observed_by_party_id),
        )
        row = cur.fetchone()
        conn.commit()
        return _row(row) or {}


def approve_benefit_distribution(
    benefit_id: str,
    approved_by_party_id: str,
    rationale: str,
) -> Dict[str, Any]:
    """Approve a benefit allocation; execution remains a separate action."""
    if not approved_by_party_id or not rationale.strip():
        raise ValueError("human approver and rationale are required")
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE coordination_benefit
               SET allocation_status = 'approved', approved_by_party_id = %s::uuid,
                   approved_at = NOW(), evidence = evidence || %s::jsonb
               WHERE id = %s::uuid AND allocation_status = 'proposed'
               RETURNING *""",
            (approved_by_party_id, json.dumps([{"type": "approval", "rationale": rationale}]), benefit_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("benefit not found or already transitioned")
        return _row(row) or {}


def record_benefit_delivery(benefit_id: str, realized_value: Optional[float] = None) -> Dict[str, Any]:
    """Record delivery of an approved benefit without performing payment."""
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE coordination_benefit
               SET allocation_status = 'delivered',
                   realized_value = COALESCE(%s, realized_value)
               WHERE id = %s::uuid AND allocation_status = 'approved'
               RETURNING *""",
            (realized_value, benefit_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("benefit must be approved before delivery is recorded")
        return _row(row) or {}


def review_risk(
    risk_id: str,
    status: str,
    reviewed_by_party_id: str,
    *,
    mitigation: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a human risk review and its current disposition."""
    if status not in {"open", "monitoring", "mitigated", "accepted", "closed"}:
        raise ValueError("invalid coordination risk status")
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE coordination_risk
               SET status = %s, mitigation = COALESCE(%s, mitigation),
                   reviewed_by_party_id = %s::uuid, reviewed_at = NOW()
               WHERE id = %s::uuid RETURNING *""",
            (status, mitigation, reviewed_by_party_id, risk_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("risk not found")
        return _row(row) or {}


def record_exchange(*args, **kwargs) -> Dict[str, Any]:
    return add_knowledge_exchange(*args, **kwargs)


def link_learning_target(
    alliance_id: str,
    link_type: str,
    title: str,
    description: str,
    *,
    target_id: str,
    baseline_value: Optional[float] = None,
    current_value: Optional[float] = None,
    target_value: Optional[float] = None,
    unit: Optional[str] = None,
    created_by_party_id: Optional[str] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    columns = {
        "capability_maturity": "capability_id",
        "process_improvement": "process_improvement_id",
        "technology_alternative": "technology_alternative_id",
        "training": "training_session_id",
        "insight_transfer": "insight_transfer_id",
        "stakeholder_outcome": "stakeholder_outcome_id",
    }
    if link_type not in columns:
        raise ValueError("invalid coordination learning link type")
    link_id = str(uuid.uuid4())
    values = {
        "id": link_id, "alliance_id": alliance_id, "link_type": link_type,
        columns[link_type]: target_id, "title": title, "description": description,
        "baseline_value": baseline_value, "current_value": current_value,
        "target_value": target_value, "unit": unit,
        "created_by_party_id": created_by_party_id, "evidence": json.dumps(evidence or []),
    }
    fields = ", ".join(values)
    placeholders = ", ".join("%s::jsonb" if key == "evidence" else "%s" for key in values)
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"INSERT INTO coordination_learning_link ({fields}) VALUES ({placeholders}) RETURNING *",
            list(values.values()),
        )
        row = cur.fetchone()
        conn.commit()
        return _row(row) or {}


def record_metric_observation(
    alliance_id: str,
    metric_key: str,
    value: float,
    unit: str,
    methodology: str,
    *,
    numerator: Optional[float] = None,
    denominator: Optional[float] = None,
    observed_by_party_id: Optional[str] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    metric_id = str(uuid.uuid4())
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO coordination_metric_observation
               (id, alliance_id, metric_key, value, numerator, denominator, unit,
                methodology, evidence, observed_by_party_id)
               VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::uuid)
               RETURNING *""",
            (metric_id, alliance_id, metric_key, value, numerator, denominator, unit,
             methodology, json.dumps(evidence or []), observed_by_party_id),
        )
        row = cur.fetchone()
        conn.commit()
        return _row(row) or {}


def _metric(value: Optional[float], unit: str, methodology: str, numerator=None, denominator=None) -> Dict[str, Any]:
    return {
        "value": round(float(value), 4) if value is not None else None,
        "unit": unit,
        "methodology": methodology,
        "numerator": numerator,
        "denominator": denominator,
    }


def explain_coordination_health(alliance_id: str) -> Dict[str, Any]:
    """Return explainable coordination metrics, never a reputation score."""
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'active') AS active FROM coordination_participant WHERE alliance_id = %s::uuid", (alliance_id,))
        participants = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'completed') AS completed FROM coordination_knowledge_exchange WHERE alliance_id = %s::uuid", (alliance_id,))
        exchanges = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) AS risks FROM coordination_risk WHERE alliance_id = %s::uuid AND status IN ('open', 'monitoring')", (alliance_id,))
        risks = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'verified' AND target_value IS NOT NULL AND current_value >= target_value) AS closed FROM coordination_learning_link WHERE alliance_id = %s::uuid AND link_type = 'capability_maturity'", (alliance_id,))
        capabilities = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE allocation_status = 'delivered') AS delivered FROM coordination_benefit WHERE alliance_id = %s::uuid", (alliance_id,))
        benefits = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) AS delivered FROM coordination_benefit WHERE alliance_id = %s::uuid AND allocation_status = 'delivered' AND participant_id IS NOT NULL GROUP BY participant_id ORDER BY delivered", (alliance_id,))
        benefit_distribution = [int(row["delivered"]) for row in cur.fetchall()]
        cur.execute("SELECT COUNT(*) AS delivered FROM coordination_contribution WHERE alliance_id = %s::uuid AND status = 'delivered'", (alliance_id,))
        contributions = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) AS delivered FROM coordination_contribution WHERE alliance_id = %s::uuid AND status = 'delivered' GROUP BY participant_id", (alliance_id,))
        contribution_distribution = [int(row["delivered"]) for row in cur.fetchall()]
        cur.execute("SELECT COUNT(*) AS failures FROM coordination_partner_event WHERE alliance_id = %s::uuid AND event_type = 'failure' AND resolved_at IS NULL", (alliance_id,))
        partner_failures = int(cur.fetchone()["failures"] or 0)
        cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE outcome IN ('on_time', 'fulfilled')) AS successful FROM coordination_market_observation WHERE alliance_id = %s::uuid", (alliance_id,))
        market_performance = dict(cur.fetchone())
        cur.execute("SELECT baseline_value, current_value FROM coordination_learning_link WHERE alliance_id = %s::uuid AND link_type = 'stakeholder_outcome' AND status = 'verified' AND baseline_value IS NOT NULL AND current_value IS NOT NULL", (alliance_id,))
        outcome_changes = [(float(row["baseline_value"]), float(row["current_value"])) for row in cur.fetchall()]
        cur.execute("SELECT EXTRACT(EPOCH FROM (MIN(lt.transitioned_at) - ca.created_at)) / 86400.0 AS days FROM coordination_alliance ca JOIN lifecycle_transition lt ON lt.entity_id = ca.id AND lt.entity_type = 'coordination_alliance' AND lt.to_status IN ('active', 'activation') WHERE ca.id = %s::uuid GROUP BY ca.created_at", (alliance_id,))
        lead = cur.fetchone()

    active_count = int(participants["active"] or 0)
    participant_total = int(participants["total"] or 0)
    exchange_total = int(exchanges["total"] or 0)
    capability_total = int(capabilities["total"] or 0)
    benefit_total = int(benefits["total"] or 0)
    delivered_contributions = int(contributions["delivered"] or 0)
    outcome_improvements = [((current - baseline) / abs(baseline) * 100) for baseline, current in outcome_changes if baseline != 0]
    contribution_total = sum(contribution_distribution)
    contribution_shares = [(count / contribution_total) for count in contribution_distribution] if contribution_total else []
    dependency_hhi = sum(share * share for share in contribution_shares) if contribution_shares else None
    benefit_equity = None
    if benefit_distribution:
        maximum = max(benefit_distribution)
        benefit_equity = (1 - ((maximum - min(benefit_distribution)) / maximum)) * 100 if maximum else 100
    return {
        "alliance_id": alliance_id,
        "interpretation": "Coordination health describes participation, exchange, delivery, learning, risk, and resilience evidence; it is not ownership or reputation.",
        "metrics": {
            "capability_gap_closed": _metric((int(capabilities["closed"] or 0) / capability_total * 100) if capability_total else None, "percent", "Verified capability-maturity links at or above target divided by capability-maturity links.", int(capabilities["closed"] or 0), capability_total),
            "knowledge_transfer_completion_rate": _metric((int(exchanges["completed"] or 0) / exchange_total * 100) if exchange_total else None, "percent", "Completed knowledge exchanges divided by recorded exchanges.", int(exchanges["completed"] or 0), exchange_total),
            "reciprocal_contribution_ratio": _metric((delivered_contributions / active_count) if active_count else None, "delivered_contributions_per_active_participant", "Delivered contribution records divided by active participants; units are not monetized.", delivered_contributions, active_count),
            "coordination_lead_time": _metric(lead["days"] if lead else None, "days", "Elapsed days from alliance creation to first recorded active transition in lifecycle_transition."),
            "unresolved_coordination_risk": _metric(int(risks["risks"] or 0), "risks", "Count of open or monitored coordination risks."),
            "benefit_distribution_equity": _metric(benefit_equity, "percent", "One minus the participant-level delivered-benefit range divided by the maximum participant delivery, expressed as a percent; unallocated benefits are excluded."),
            "stakeholder_outcome_improvement": _metric(sum(outcome_improvements) / len(outcome_improvements) if outcome_improvements else None, "percent", "Mean relative change from verified stakeholder-outcome baseline to current value across linked outcome records."),
            "dependency_concentration": _metric(dependency_hhi, "hhi", "Herfindahl-Hirschman concentration of delivered contribution records by participant; higher values indicate more concentration."),
            "partner_substitution_resilience": _metric((active_count / participant_total * 100) if participant_total else None, "percent", "Active participants divided by all recorded participants; this is a structural resilience signal, not a partner score.", active_count, participant_total),
            "partner_failure_count": _metric(partner_failures, "events", "Unresolved partner failure events recorded for the alliance; this is a review signal, not a partner score."),
            "market_performance_success_rate": _metric((int(market_performance["successful"] or 0) / int(market_performance["total"]) * 100) if market_performance["total"] else None, "percent", "On-time or fulfilled market observations divided by all recorded market observations.", int(market_performance["successful"] or 0), int(market_performance["total"] or 0)),
        },
    }


def list_metric_observations(alliance_id: str, metric_key: Optional[str] = None) -> List[Dict[str, Any]]:
    where = "alliance_id = %s::uuid"
    params: List[Any] = [alliance_id]
    if metric_key:
        where += " AND metric_key = %s"
        params.append(metric_key)
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM coordination_metric_observation WHERE {where} ORDER BY as_of DESC", params)
        return [_row(row) or {} for row in cur.fetchall()]
