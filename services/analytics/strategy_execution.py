"""Integrated strategy execution rollups and review snapshots."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def dashboard(conn, *, strategy_plan_id: Optional[str] = None, scope_type: Optional[str] = None, scope_id: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params = []
    if strategy_plan_id:
        clauses.append("strategy_plan_id = %s::uuid")
        params.append(strategy_plan_id)
    if scope_type:
        clauses.append("scope_type = %s")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = %s::uuid")
        params.append(scope_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_strategy_kernel_execution{where} ORDER BY scope_type, scope_id, version DESC", params)
        return [_clean(row) for row in cur.fetchall()]


def capture_snapshot(conn, strategy_plan_id: str, *, captured_by_party_id: Optional[str] = None, review_note: Optional[str] = None) -> Dict[str, Any]:
    rows = dashboard(conn, strategy_plan_id=strategy_plan_id)
    if not rows:
        raise ValueError("strategy plan execution state not found")
    summary = rows[0]
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_review_snapshot
            (strategy_plan_id, captured_by_party_id, summary, review_note)
            VALUES (%s::uuid, %s::uuid, %s::jsonb, %s) RETURNING *""", (strategy_plan_id, captured_by_party_id, json.dumps(summary, default=str), review_note))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def list_snapshots(conn, strategy_plan_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM strategy_review_snapshot WHERE strategy_plan_id = %s::uuid ORDER BY captured_at DESC", (strategy_plan_id,))
        return [_clean(row) for row in cur.fetchall()]


def calculate_variance(planned_value: Optional[float], actual_value: Optional[float]) -> Dict[str, Any]:
    if planned_value is None or actual_value is None:
        return {"variance_value": None, "variance_pct": None, "status": "not_measurable"}
    variance = float(actual_value) - float(planned_value)
    pct = (variance / abs(float(planned_value)) * 100) if planned_value else None
    status = "within_tolerance" if pct is not None and abs(pct) <= 10 else "warning" if pct is not None and abs(pct) <= 25 else "breach"
    return {"variance_value": round(variance, 4), "variance_pct": round(pct, 2) if pct is not None else None, "status": status}


def record_benefit(conn, strategy_plan_id: str, name: str, benefit_type: str, *, investment_id: Optional[str] = None, initiative_id: Optional[str] = None, baseline_value: Optional[float] = None, target_value: Optional[float] = None, expected_value: Optional[float] = None, actual_value: Optional[float] = None, unit: Optional[str] = None, direction: str = "gte", owner_party_id: Optional[str] = None, realization_due_at: Optional[str] = None, evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    if actual_value is None:
        status = "planned"
    elif target_value is not None and ((direction == "gte" and actual_value >= target_value) or (direction == "lte" and actual_value <= target_value)):
        status = "realized"
    else:
        status = "not_realized"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_benefit
            (strategy_plan_id, investment_id, initiative_id, name, benefit_type, baseline_value, target_value, expected_value, actual_value, unit, direction, status, owner_party_id, realization_due_at, evidence)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s, %s::jsonb) RETURNING *""", (strategy_plan_id, investment_id, initiative_id, name, benefit_type, baseline_value, target_value, expected_value, actual_value, unit, direction, status, owner_party_id, realization_due_at, json.dumps(evidence or [])))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def compare_snapshots(conn, strategy_plan_id: str) -> Dict[str, Any]:
    snapshots = list_snapshots(conn, strategy_plan_id)
    if len(snapshots) < 2:
        return {"strategy_plan_id": strategy_plan_id, "available": False, "reason": "at least two snapshots are required"}
    current = snapshots[0]["summary"]
    previous = snapshots[1]["summary"]
    numeric_keys = ("objective_count", "measured_objective_count", "initiative_count", "completed_initiative_count", "average_initiative_completion_pct", "investment_case_count", "recommended_investment_count", "average_investment_score", "open_coherence_finding_count", "critical_coherence_finding_count", "benefit_count", "benefit_risk_count")
    changes = {key: {"previous": previous.get(key), "current": current.get(key), "delta": float(current[key]) - float(previous[key])} for key in numeric_keys if current.get(key) is not None and previous.get(key) is not None}
    return {"strategy_plan_id": strategy_plan_id, "available": True, "current_snapshot_id": snapshots[0]["id"], "previous_snapshot_id": snapshots[1]["id"], "changes": changes}


def create_review_task(conn, strategy_plan_id: str, due_at: str, review_type: str = "scheduled", *, assigned_to_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_review_task
            (strategy_plan_id, review_type, due_at, assigned_to_party_id)
            VALUES (%s::uuid, %s, %s, %s::uuid) RETURNING *""", (strategy_plan_id, review_type, due_at, assigned_to_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def list_due_reviews(conn) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_review_task SET status = 'overdue', updated_at = NOW()
            WHERE status = 'pending' AND due_at < NOW()""")
        cur.execute("SELECT * FROM strategy_review_task WHERE status IN ('pending', 'overdue') ORDER BY due_at")
        rows = [_clean(row) for row in cur.fetchall()]
        conn.commit()
        return rows


def complete_review_task(conn, task_id: str, completed_by_party_id: str, decision: str, *, decision_note: str = "", evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    if decision not in ("continue", "adapt", "stop", "replace", "scale", "defer", "investigate"):
        raise ValueError("invalid strategy review decision")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_review_task SET status = 'completed', decision = %s,
            decision_note = %s, evidence = %s::jsonb, completed_at = NOW(), completed_by_party_id = %s::uuid,
            updated_at = NOW() WHERE id = %s::uuid AND status IN ('pending', 'in_progress', 'overdue') RETURNING *""", (decision, decision_note, json.dumps(evidence or []), completed_by_party_id, task_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("review task not found or already completed")
        conn.commit()
        return _clean(row)
