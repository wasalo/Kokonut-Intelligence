"""Agent safety helpers for bounded write and audit behavior."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from services.agents.logging import log_agent_action

HIGH_RISK_ACTIONS = {
    "publish",
    "attest",
    "onchain_submit",
    "delete",
    "bulk_update",
    "financial_write",
    "status_change_to_published",
}

AGENT_ALLOWED_REVIEW_STATUSES = {"draft", "submitted", "rejected"}
AGENT_ALLOWED_SUMMARY_STATUSES = {"draft", "submitted", "rejected"}
AGENT_ALLOWED_EBF_STATUSES = {"draft", "submitted", "rejected"}

GOVERNED_COLLECTIONS = {
    "ai_summary",
    "agent_task",
    "ebf_scorecard",
    "ebf_score",
    "ebf_calibration_decision",
    "stakeholder_feedback",
    "stakeholder_feedback_review",
    "impact_claim",
    "metric_proposal",
    "stakeholder_outcome",
    "cultural_context_record",
    "wellbeing_metric_observation",
    "participatory_action_record",
    "financial_sustainability_plan",
    "risk_mitigation_register",
    "scaling_roadmap_milestone",
    "green_paper_publication_review",
    "capital_efficiency_scenario",
    "regenerative_efficiency_observation",
    "governance_throughput_observation",
    "capital_provider_utility_scenario",
    "time_liberation_observation",
    "capital_alignment_assessment",
    "governance_inclusion_observation",
    "land_stewardship_commitment",
    "gnh_alignment_assessment",
    "cultural_preservation_plan",
    "renewable_energy_plan",
    "vulnerable_group_access_plan",
    "foundational_wellbeing_observation",
    "regenerative_outcome_summary",
    "community_governance_mechanism",
    "replication_readiness_assessment",
    "adaptive_stewardship_review",
    "farm_launch_unit_economics",
    "network_scaling_target",
    "adoption_barrier_assessment",
    "perpetual_value_stress_test",
    "open_source_impact_artifact",
    "anti_capture_governance_policy",
    "commons_redistribution_policy",
    "federation_protocol",
    "algorithmic_redistribution_mechanism",
    "participatory_signal_experiment",
    "bio_factory_batch",
    "bio_input_provenance",
    "bio_recipe_library",
    "bio_factory_distribution",
    "bio_factory_quality_test",
    "bio_ingredient_composition_reference",
    "bio_regional_input_availability",
    "carbon_credit",
    "credit_adjustment",
    "credit_retirement",
    "credit_transfer",
}


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    high_risk: bool
    requires_human_approval: bool
    reason: str


def payload_hash(payload: Optional[dict[str, Any]]) -> Optional[str]:
    """Return a stable SHA-256 hash for audit logging."""
    if payload is None:
        return None
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assess_agent_action(action: str, collection: str, payload: Optional[dict[str, Any]] = None) -> SafetyDecision:
    """Assess whether an agent action is allowed before writing."""
    payload = payload or {}
    high_risk = action in HIGH_RISK_ACTIONS

    if collection == "agent_task":
        review_status = payload.get("review_status")
        if review_status and review_status not in AGENT_ALLOWED_REVIEW_STATUSES:
            return SafetyDecision(False, True, True, "agents cannot verify or publish agent_task records")

    if collection == "ai_summary":
        status = payload.get("status")
        if status and status not in AGENT_ALLOWED_SUMMARY_STATUSES:
            return SafetyDecision(False, True, True, "agents cannot verify or publish ai_summary records")

    if collection in {"ebf_scorecard", "ebf_calibration_decision"}:
        status = payload.get("status") or payload.get("decision_status")
        if status and status not in AGENT_ALLOWED_EBF_STATUSES:
            return SafetyDecision(False, True, True, f"agents cannot verify or publish {collection} records")

    if collection in {"ebf_scorecard", "ebf_score"}:
        maturity = payload.get("evidence_maturity_level")
        if maturity is not None:
            try:
                maturity_level = int(maturity)
            except (TypeError, ValueError):
                return SafetyDecision(False, True, True, "invalid EBF evidence maturity level")
            if maturity_level > 3:
                return SafetyDecision(False, True, True, "agents cannot raise EBF evidence maturity to public-claim levels")

    if collection in GOVERNED_COLLECTIONS and collection not in {"agent_task", "ai_summary", "ebf_scorecard", "ebf_calibration_decision", "ebf_score"}:
        status = payload.get("status") or payload.get("policy_status") or payload.get("protocol_status") or payload.get("implementation_status") or payload.get("experiment_status")
        if status and status not in AGENT_ALLOWED_REVIEW_STATUSES:
            return SafetyDecision(False, True, True, f"agents cannot verify or publish {collection} records")

    if action == "status_change_to_published":
        return SafetyDecision(False, True, True, "agents cannot publish records directly")

    return SafetyDecision(True, high_risk, high_risk, "allowed")


def assert_agent_action_allowed(action: str, collection: str, payload: Optional[dict[str, Any]] = None) -> SafetyDecision:
    """Raise ValueError when the action violates Kokonut agent safety rules."""
    decision = assess_agent_action(action, collection, payload)
    if not decision.allowed:
        raise ValueError(decision.reason)
    return decision


def audit_agent_action(
    agent_id: str,
    action: str,
    collection: str,
    payload: Optional[dict[str, Any]] = None,
    task_id: Optional[str] = None,
    record_id: Optional[str] = None,
    action_result: str = "success",
    error_message: Optional[str] = None,
) -> str:
    """Assess and write an agent_action_log entry."""
    decision = assess_agent_action(action, collection, payload)
    return log_agent_action(
        agent_id=agent_id,
        task_id=task_id,
        action=action,
        collection=collection,
        record_id=record_id,
        payload_hash=payload_hash(payload),
        action_result=action_result,
        error_message=error_message,
        metadata={
            "allowed": decision.allowed,
            "reason": decision.reason,
            "requires_human_approval": decision.requires_human_approval,
        },
    )
