"""Canonical solution lifecycle and stage-gate operations."""

from __future__ import annotations

from typing import Any, Dict, Optional

STAGES = ("discovered", "triaged", "framed", "experiment_ready", "testing", "validated", "investment_ready", "funded", "pilot_active", "adoption_ready", "adopting", "scaled", "maintained", "paused", "superseded", "retired", "failed")
PROMOTION_GATES = {"validated", "funded", "adoption_ready", "scaled"}
ADOPTION_PROGRAM_READY = ("enablement_ready", "launch", "onboarding", "active", "assessed", "expand")


def create_solution(conn, canonical_key: str, name: str, solution_type: str, problem_statement: str, *, theory_of_change: Optional[str] = None, baseline_alternative: Optional[str] = None, owner_party_id: Optional[str] = None, created_by_party_id: Optional[str] = None, risk_class: str = "medium", reversibility: str = "medium") -> Dict[str, Any]:
    del conn, canonical_key, name, solution_type, problem_statement
    del theory_of_change, baseline_alternative, owner_party_id, created_by_party_id
    del risk_class, reversibility
    raise ValueError("solution creation requires an authenticated location-scoped Gateway grant")


def add_link(conn, solution_id: str, entity_type: str, entity_id: str, relationship: str, *, rationale: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    del conn, solution_id, entity_type, entity_id, relationship, rationale, created_by_party_id
    raise ValueError("solution links require an authenticated location-scoped sharing workflow")


def create_gate(conn, solution_id: str, from_stage: str, to_stage: str, *, required_evidence_maturity: Optional[int] = None, required_experiment_count: int = 0, requirements: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
    del conn, solution_id, from_stage, to_stage
    del required_evidence_maturity, required_experiment_count, requirements
    raise ValueError("stage gate definition requires an authenticated location-scoped Gateway grant")


def approve_gate(conn, gate_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    del conn, gate_id, approved_by_party_id
    raise ValueError(
        "gate approval requires an authenticated location-scoped Gateway grant"
    )


def evaluate_gate(conn, gate_id: str, passed: bool, evaluated_by_party_id: str, *, observed: Optional[dict[str, Any]] = None, evidence: Optional[list[Any]] = None) -> Dict[str, Any]:
    del conn, gate_id, passed, evaluated_by_party_id, observed, evidence
    raise ValueError(
        "gate evaluations require an authenticated location-scoped Gateway grant"
    )


def transition(conn, solution_id: str, to_stage: str, actor_party_id: Optional[str] = None, *, approved_by_party_id: Optional[str] = None, rationale: str, evidence: Optional[list[Any]] = None, rollback_plan: Optional[str] = None) -> Dict[str, Any]:
    del conn, solution_id, actor_party_id, approved_by_party_id, rationale, evidence, rollback_plan
    if to_stage not in STAGES:
        raise ValueError("invalid solution stage")
    if to_stage == "retired":
        raise ValueError(
            "retirement must use the authenticated location-scoped execution and sunset workflow"
        )
    raise ValueError(
        "stage transitions require an authenticated location-scoped Gateway grant"
    )
