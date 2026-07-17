"""Scale gates, learning transfer, and retirement workflow."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_gate(conn, solution_id: str, scope_type: str, scope_id: str, gate_type: str, requirement: str, *, threshold: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_scale_gate
            (solution_id, scope_type, scope_id, gate_type, requirement, threshold)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s)
            ON CONFLICT (solution_id, scope_type, scope_id, gate_type) DO UPDATE SET requirement = EXCLUDED.requirement, threshold = EXCLUDED.threshold
            RETURNING *""", (solution_id, scope_type, scope_id, gate_type, requirement, threshold))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def evaluate_gate(conn, gate_id: str, passed: bool, measured_value: str, evidence_refs: list[Any], approved_by_party_id: str) -> Dict[str, Any]:
    if not evidence_refs:
        raise ValueError("scale gate evaluation requires evidence")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT comparison_operator, threshold_numeric FROM solution_scale_gate WHERE id = %s::uuid", (gate_id,))
        contract = cur.fetchone()
        if not contract:
            conn.rollback()
            raise ValueError("scale gate not found")
        if contract["comparison_operator"] and contract["threshold_numeric"] is not None:
            try:
                observed_value = float(measured_value)
                threshold = float(contract["threshold_numeric"])
            except (TypeError, ValueError):
                conn.rollback()
                raise ValueError("typed scale gate requires a numeric measured value")
            passed = {"lt": observed_value < threshold, "lte": observed_value <= threshold, "eq": observed_value == threshold, "gte": observed_value >= threshold, "gt": observed_value > threshold}[contract["comparison_operator"]]
        cur.execute("""UPDATE solution_scale_gate SET status = %s, measured_value = %s,
            evidence_refs = %s::jsonb, approved_by_party_id = %s::uuid, approved_at = NOW()
            WHERE id = %s::uuid RETURNING *""", ("passed" if passed else "failed", measured_value, json.dumps(evidence_refs), approved_by_party_id, gate_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("scale gate not found")
        conn.commit()
        return _clean(row)


def record_learning(conn, solution_id: str, lesson_type: str, finding: str, recommended_action: str, *, source_experiment_id: Optional[str] = None, source_replication_id: Optional[str] = None, confidence: str = "moderate", transferability: str = "unknown", affected_assumptions: Optional[list[Any]] = None, affected_metrics: Optional[list[Any]] = None, evidence: Optional[list[Any]] = None, owner_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_learning_record
            (solution_id, source_experiment_id, source_replication_id, lesson_type, finding,
             confidence, transferability, affected_assumptions, affected_metrics, recommended_action, evidence, owner_party_id)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::uuid) RETURNING *""", (solution_id, source_experiment_id, source_replication_id, lesson_type, finding, confidence, transferability, json.dumps(affected_assumptions or []), json.dumps(affected_metrics or []), recommended_action, json.dumps(evidence or []), owner_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def apply_learning(conn, learning_id: str, applied_to_version: str, owner_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE solution_learning_record SET decision_status = 'applied', applied_to_version = %s, owner_party_id = %s::uuid WHERE id = %s::uuid AND decision_status IN ('proposed', 'accepted') RETURNING *", (applied_to_version, owner_party_id, learning_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("learning record is not available for application")
        conn.commit()
        return _clean(row)


def propose_retirement(conn, solution_id: str, retirement_type: str, trigger_reason: str, *, evidence_refs: Optional[list[Any]] = None, migration_plan: Optional[str] = None, replacement_solution_id: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_retirement
            (solution_id, retirement_type, trigger_reason, evidence_refs, migration_plan, replacement_solution_id, created_by_party_id)
            VALUES (%s::uuid, %s, %s, %s::jsonb, %s, %s::uuid, %s::uuid) RETURNING *""", (solution_id, retirement_type, trigger_reason, json.dumps(evidence_refs or []), migration_plan, replacement_solution_id, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def approve_retirement(conn, retirement_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT evidence_refs, retirement_type, migration_plan, replacement_solution_id FROM solution_retirement WHERE id = %s::uuid FOR UPDATE", (retirement_id,))
        retirement = cur.fetchone()
        if not retirement:
            conn.rollback()
            raise ValueError("retirement not found")
        if not retirement["evidence_refs"]:
            conn.rollback()
            raise ValueError("retirement approval requires evidence")
        if retirement["retirement_type"] == "superseded" and not retirement["replacement_solution_id"]:
            conn.rollback()
            raise ValueError("superseded retirement requires a replacement solution")
        if not retirement["migration_plan"]:
            conn.rollback()
            raise ValueError("retirement approval requires a migration plan")
        cur.execute("""UPDATE solution_retirement SET status = 'approved', approved_by_party_id = %s::uuid, approved_at = NOW()
            WHERE id = %s::uuid AND status IN ('proposed', 'impact_review') RETURNING *""", (approved_by_party_id, retirement_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only proposed or reviewed retirements can be approved")
        conn.commit()
        return _clean(row)
