"""Scale gates, learning transfer, and retirement workflow."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_gate(conn, solution_id: str, scope_type: str, scope_id: str, gate_type: str, requirement: str, *, threshold: Optional[str] = None) -> Dict[str, Any]:
    del conn, solution_id, scope_type, scope_id, gate_type, requirement, threshold
    raise ValueError(
        "scale-gate changes require an authenticated location-scoped Gateway grant"
    )


def evaluate_gate(conn, gate_id: str, passed: bool, measured_value: str, evidence_refs: list[Any], approved_by_party_id: str) -> Dict[str, Any]:
    del conn, gate_id, passed, measured_value, evidence_refs, approved_by_party_id
    raise ValueError(
        "scale-gate evaluations require an authenticated location-scoped Gateway grant"
    )


def record_learning(conn, solution_id: str, lesson_type: str, finding: str, recommended_action: str, *, source_experiment_id: Optional[str] = None, source_replication_id: Optional[str] = None, confidence: str = "moderate", transferability: str = "unknown", affected_assumptions: Optional[list[Any]] = None, affected_metrics: Optional[list[Any]] = None, evidence: Optional[list[Any]] = None, owner_party_id: Optional[str] = None) -> Dict[str, Any]:
    del conn, solution_id, lesson_type, finding, recommended_action
    del source_experiment_id, source_replication_id, confidence, transferability
    del affected_assumptions, affected_metrics, evidence, owner_party_id
    raise ValueError(
        "learning proposals require an authenticated location-scoped Gateway grant"
    )


def apply_learning(conn, learning_id: str, applied_to_version: str, owner_party_id: str) -> Dict[str, Any]:
    del conn, learning_id, applied_to_version, owner_party_id
    raise ValueError(
        "learning application requires an authenticated location-scoped Gateway grant"
    )


def propose_retirement(conn, solution_id: str, retirement_type: str, trigger_reason: str, *, evidence_refs: Optional[list[Any]] = None, migration_plan: Optional[str] = None, replacement_solution_id: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if not created_by_party_id:
        raise ValueError("retirement proposal requires an attributed proposer")
    del conn, solution_id, retirement_type, trigger_reason, evidence_refs
    del migration_plan, replacement_solution_id, created_by_party_id
    raise ValueError(
        "retirement proposals require an authenticated location-scoped Gateway grant"
    )


def approve_retirement(conn, retirement_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    del conn, retirement_id, approved_by_party_id
    raise ValueError(
        "retirement approvals require an authenticated location-scoped Gateway grant"
    )
