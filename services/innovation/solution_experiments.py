"""Governed solution experiments and replication records."""

from __future__ import annotations

from typing import Any, Dict, Optional


def create_experiment(conn, solution_id: str, hypothesis: str, baseline_definition: str, treatment_definition: str, unit_of_analysis: str, rollback_plan: str, *, null_hypothesis: Optional[str] = None, comparator_definition: Optional[str] = None, primary_metric_keys: Optional[list[str]] = None, secondary_metric_keys: Optional[list[str]] = None, sample_plan: Optional[dict[str, Any]] = None, stopping_rules: Optional[dict[str, Any]] = None, safety_boundaries: Optional[dict[str, Any]] = None, consent_requirements: Optional[dict[str, Any]] = None, owner_party_id: Optional[str] = None) -> Dict[str, Any]:
    del (
        conn, solution_id, hypothesis, baseline_definition, treatment_definition,
        unit_of_analysis, rollback_plan, null_hypothesis, comparator_definition,
        primary_metric_keys, secondary_metric_keys, sample_plan, stopping_rules,
        safety_boundaries, consent_requirements, owner_party_id,
    )
    raise RuntimeError(
        "Direct experiment creation is disabled; create protocol drafts through the "
        "location-scoped Solution Lifecycle Gateway"
    )


def submit_protocol(conn, experiment_id: str) -> Dict[str, Any]:
    del conn, experiment_id
    raise RuntimeError(
        "Direct experiment submission is disabled; submit protocols through the "
        "location-scoped Solution Lifecycle Gateway"
    )


def approve_protocol(conn, experiment_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    del conn, experiment_id, approved_by_party_id
    raise RuntimeError(
        "Direct experiment approval is disabled; review and approve protocols through the "
        "location-scoped Solution Lifecycle Gateway"
    )


def start_experiment(conn, experiment_id: str, started_by_party_id: str) -> Dict[str, Any]:
    del conn, experiment_id, started_by_party_id
    raise RuntimeError(
        "Direct experiment start is disabled; start protocols through the "
        "location-scoped Solution Lifecycle Gateway"
    )


def record_observation(conn, experiment_id: str, metric_key: str, value: Optional[float], arm: str, *, unit_ref: Optional[str] = None, adverse_event: bool = False, evidence: Optional[dict[str, Any]] = None, recorded_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    del (
        conn, experiment_id, metric_key, value, arm, unit_ref,
        adverse_event, evidence, recorded_by_party_id,
    )
    raise RuntimeError(
        "Direct experiment observations are disabled until collection uses a "
        "consent-aware, location-scoped Solution Lifecycle Gateway path"
    )


def complete_experiment(conn, experiment_id: str) -> Dict[str, Any]:
    del conn, experiment_id
    raise RuntimeError(
        "Direct experiment completion is disabled until analysis and completion "
        "use the location-scoped Solution Lifecycle Gateway"
    )


def analyze_sequentially(conn, experiment_id: str, metric_key: str, *, minimum_sample: int = 2, benefit_threshold: float = 0.0, posterior_threshold: float = 0.9, safety_event_limit: Optional[int] = None, analysis_version: str = "sequential-v1") -> Dict[str, Any]:
    del (
        conn, experiment_id, metric_key, minimum_sample, benefit_threshold,
        posterior_threshold, safety_event_limit, analysis_version,
    )
    raise RuntimeError(
        "Direct sequential experiment analysis is disabled until it uses a "
        "location-scoped Solution Lifecycle Gateway path"
    )


def review_result(conn, experiment_id: str, outcome: str, reviewed_by_party_id: str, *, primary_results: Optional[dict[str, Any]] = None, secondary_results: Optional[dict[str, Any]] = None, limitations: Optional[str] = None, evidence: Optional[list[Any]] = None) -> Dict[str, Any]:
    del (
        conn, experiment_id, outcome, reviewed_by_party_id, primary_results,
        secondary_results, limitations, evidence,
    )
    raise RuntimeError(
        "Direct experiment-result review is disabled; use the "
        "location-scoped Solution Lifecycle Gateway"
    )


def create_replication(conn, solution_id: str, source_experiment_id: str, target_scope_type: str, target_scope_id: str, target_context: str, *, adaptation_required: Optional[str] = None, context_similarity: Optional[float] = None) -> Dict[str, Any]:
    del (
        conn, solution_id, source_experiment_id, target_scope_type,
        target_scope_id, target_context, adaptation_required, context_similarity,
    )
    raise RuntimeError(
        "Direct experiment replication writes are disabled; propose replication "
        "through the location-scoped Solution Lifecycle Gateway"
    )
