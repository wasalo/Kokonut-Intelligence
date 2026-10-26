"""Solution adoption journeys, local configurations, and readiness."""

from __future__ import annotations

from typing import Any, Dict, Optional


def create_program(conn, solution_id: str, target_scope_type: str, target_scope_id: str, adoption_pathway: str, *, target_population: Optional[dict[str, Any]] = None, local_adaptation_policy: Optional[str] = None, champion_party_id: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    del conn, solution_id, target_scope_type, target_scope_id, adoption_pathway
    del target_population, local_adaptation_policy, champion_party_id, created_by_party_id
    raise RuntimeError(
        "legacy adoption program creation is disabled; use the exact-location "
        "solution-lifecycle Gateway draft action"
    )


def assess_readiness(conn, solution_id: str, adopter_scope_type: str, adopter_scope_id: str, current_level: float, required_level: float, *, remediation_plan: Optional[str] = None, assessed_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    del conn, solution_id, adopter_scope_type, adopter_scope_id, current_level
    del required_level, remediation_plan, assessed_by_party_id
    raise RuntimeError(
        "legacy readiness assessment is disabled pending a location-scoped "
        "proposal and independent review action"
    )


def approve_configuration(conn, solution_id: str, scope_type: str, scope_id: str, invariant_components: dict[str, Any], configurable_components: dict[str, Any], *, prohibited_components: Optional[dict[str, Any]] = None, local_assumptions: Optional[dict[str, Any]] = None, adaptation_owner_party_id: Optional[str] = None, comparability_class: str = "comparable", evidence_impact: Optional[str] = None, approved_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    del conn, solution_id, scope_type, scope_id, invariant_components
    del configurable_components, prohibited_components, local_assumptions
    del adaptation_owner_party_id, comparability_class, evidence_impact
    del approved_by_party_id
    raise RuntimeError(
        "legacy configuration approval is disabled; configuration proposals "
        "require a location-scoped draft and independent review action"
    )


def record_event(conn, program_id: str, adopter_ref: str, event_type: str, *, cohort_id: Optional[str] = None, fidelity_score: Optional[float] = None, support_required: Optional[str] = None, outcome: Optional[dict[str, Any]] = None, consent_checked: bool = False, evidence: Optional[dict[str, Any]] = None, recorded_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    del conn, program_id, adopter_ref, event_type, cohort_id, fidelity_score
    del support_required, outcome, consent_checked, evidence, recorded_by_party_id
    raise ValueError(
        "adoption events require a consent-aware, location-scoped Gateway path"
    )
