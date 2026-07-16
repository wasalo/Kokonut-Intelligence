"""Versioned strategy kernel for organization and location scopes."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


SCOPES = ("organization", "location")
STATUSES = ("draft", "submitted", "approved", "active", "superseded", "retired")
APPROVAL_MODES = ("governance_circle", "stakeholder_decision", "dual")


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_strategy_plan(
    conn, scope_type: str, scope_id: str, name: str,
    planning_horizon_start: str, planning_horizon_end: str, created_by_party_id: Optional[str] = None,
    *, diagnosis_summary: str = "", guiding_policy: str = "", theory_of_change: Optional[str] = None,
    uncertainty_summary: Optional[str] = None, approval_mode: str = "governance_circle",
    visibility: str = "private", supersedes_plan_id: Optional[str] = None,
    parent_strategy_plan_id: Optional[str] = None, cascade_mode: str = "independent",
    cascade_rationale: Optional[str] = None,
) -> Dict[str, Any]:
    if scope_type not in SCOPES:
        raise ValueError(f"scope_type must be one of {SCOPES}")
    if approval_mode not in APPROVAL_MODES:
        raise ValueError(f"approval_mode must be one of {APPROVAL_MODES}")
    if visibility not in ("private", "limited", "public"):
        raise ValueError("invalid visibility")
    if not name.strip():
        raise ValueError("name is required")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"strategy-plan:{scope_type}:{scope_id}",))
        if supersedes_plan_id:
            cur.execute("SELECT scope_type, scope_id FROM strategy_plan WHERE id = %s::uuid", (supersedes_plan_id,))
            predecessor = cur.fetchone()
            if not predecessor or predecessor["scope_type"] != scope_type or str(predecessor["scope_id"]) != str(scope_id):
                conn.rollback()
                raise ValueError("superseded strategy plan must use the same scope")
        cur.execute("""SELECT COALESCE(MAX(version), 0) + 1 AS next_version
            FROM strategy_plan WHERE scope_type = %s AND scope_id = %s::uuid""", (scope_type, scope_id))
        version = cur.fetchone()["next_version"]
        cur.execute("""INSERT INTO strategy_plan
            (scope_type, scope_id, name, version, planning_horizon_start, planning_horizon_end,
            diagnosis_summary, guiding_policy, theory_of_change, uncertainty_summary,
            approval_mode, visibility, supersedes_plan_id, created_by_party_id,
            parent_strategy_plan_id, cascade_mode, cascade_rationale)
            VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s::uuid, %s::uuid, %s, %s)
            RETURNING *""", (scope_type, scope_id, name, version, planning_horizon_start, planning_horizon_end,
                              diagnosis_summary, guiding_policy, theory_of_change, uncertainty_summary,
                              approval_mode, visibility, supersedes_plan_id, created_by_party_id,
                              parent_strategy_plan_id, cascade_mode, cascade_rationale))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def submit_strategy_plan(conn, plan_id: str) -> Dict[str, Any]:
    return _transition(conn, plan_id, "submitted")


def approve_strategy_plan(conn, plan_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT approval_mode FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
        plan_route = cur.fetchone()
        if not plan_route:
            conn.rollback()
            raise ValueError("strategy plan not found")
        from services.analytics.strategy_governance import approval_route_satisfied
        from services.analytics.strategy_coherence import run_checks, list_findings
        run_checks(conn, plan_id)
        if any(finding["severity"] == "critical" for finding in list_findings(conn, plan_id)):
            conn.rollback()
            raise ValueError("strategy plan has unresolved critical coherence findings")
        if not approval_route_satisfied(conn, plan_id, plan_route["approval_mode"]):
            conn.rollback()
            raise ValueError("strategy approval route is not satisfied")
        cur.execute("""UPDATE strategy_plan
            SET status = 'approved', approved_by_party_id = %s::uuid, approved_at = NOW(), updated_at = NOW()
            WHERE id = %s::uuid AND status = 'submitted' RETURNING *""", (approved_by_party_id, plan_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only submitted strategy plans can be approved")
        conn.commit()
        _record_transition(conn, plan_id, "submitted", "approved", approved_by_party_id, "Strategy plan approved after integrity gates")
        return _clean(row)


def activate_strategy_plan(conn, plan_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM strategy_plan WHERE id = %s::uuid FOR UPDATE", (plan_id,))
        plan = cur.fetchone()
        if not plan or plan["status"] != "approved":
            conn.rollback()
            raise ValueError("only approved strategy plans can be activated")
        cur.execute("""UPDATE strategy_plan SET status = 'superseded', updated_at = NOW()
            WHERE scope_type = %s AND scope_id = %s AND status = 'active'""", (plan["scope_type"], plan["scope_id"]))
        cur.execute("UPDATE strategy_plan SET status = 'active', updated_at = NOW() WHERE id = %s::uuid RETURNING *", (plan_id,))
        row = _clean(cur.fetchone())
        conn.commit()
        _record_transition(conn, plan_id, "approved", "active", None, "Strategy plan activated")
        return row


def list_strategy_plans(conn, *, scope_type: Optional[str] = None, scope_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if scope_type:
        clauses.append("scope_type = %s")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = %s::uuid")
        params.append(scope_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM strategy_plan{where} ORDER BY scope_type, scope_id, version DESC", params)
        return [_clean(row) for row in cur.fetchall()]


def attach_strategy_entry(conn, strategy_plan_id: str, strategy_map_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_map SET strategy_plan_id = %s::uuid, updated_at = NOW()
            WHERE id = %s::uuid RETURNING *""", (strategy_plan_id, strategy_map_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("strategy map entry not found")
        conn.commit()
        return _clean(row)


def _transition(conn, plan_id: str, status: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE strategy_plan SET status = %s, updated_at = NOW() WHERE id = %s::uuid AND status = 'draft' RETURNING *", (status, plan_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only draft strategy plans can be submitted")
        conn.commit()
        _record_transition(conn, plan_id, "draft", status, None, "Strategy plan submitted")
        return _clean(row)


def _record_transition(conn, plan_id: str, from_status: str, to_status: str, actor_party_id: Optional[str], reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO strategy_plan_transition
            (strategy_plan_id, from_status, to_status, actor_party_id, reason)
            VALUES (%s::uuid, %s, %s, %s::uuid, %s)""", (plan_id, from_status, to_status, actor_party_id, reason))
    conn.commit()
