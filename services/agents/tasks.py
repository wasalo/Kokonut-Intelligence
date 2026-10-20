"""Agent task catalogue and output schema helpers."""

from __future__ import annotations

import argparse
import json
import math
import re
from copy import deepcopy
from typing import Any
from uuid import UUID

TASK_CATALOGUE: dict[str, dict[str, Any]] = {
    "cids_export": {
        "description": "Prepare a CIDS v3.2.0 Essential Tier JSON-LD export for one location.",
        "risk": "low",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": True},
        },
        "outputs": {
            "document": {"type": "object", "required": True},
            "graph_count": {"type": "integer", "required": True},
            "alignment_tier": {"type": "string", "required": True},
            "cids_version": {"type": "string", "required": True},
        },
        "writes": [],
        "high_risk": False,
    },
    "feedback_synthesis": {
        "description": "Summarize stakeholder feedback using public summaries and aggregate private-feedback signals.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": True},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "public_interest_report_context": {
        "description": "Prepare report limitations, public stakeholder voice, and evidence gap context.",
        "risk": "low",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": True},
        },
        "outputs": {
            "public_interest": {"type": "object", "required": True},
        },
        "writes": [],
        "high_risk": False,
    },
    "holistic_wellbeing_synthesis": {
        "description": "Summarize public-safe cultural context, well-being metrics, language coverage, and participatory actions.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": True},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "financial_resilience_synthesis": {
        "description": "Summarize public-safe financial sustainability, risk mitigation, scaling roadmap, and Green Paper publication status.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "capital_efficiency_synthesis": {
        "description": "Summarize public-safe capital efficiency, regenerative payback, governance throughput, and capital-provider utility scenarios.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "commons_liberation_synthesis": {
        "description": "Summarize public-safe time liberation, capital alignment, governance inclusion, and land stewardship evidence.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "gnh_alignment_synthesis": {
        "description": "Summarize public-safe GNH alignment, cultural preservation, renewable energy, vulnerable access, and foundational well-being evidence.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "regenerator_synthesis": {
        "description": "Summarize public-safe regenerative outcomes, community governance, replication readiness, and adaptive stewardship evidence.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "open_source_capitalist_synthesis": {
        "description": "Summarize public-safe scaling economics, adoption barriers, perpetual-value stress tests, and open-source reuse evidence.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "kokonut_commons_synthesis": {
        "description": "Summarize public-safe anti-capture governance, flexible redistribution policies, federation protocols, algorithmic redistribution mechanisms, and participatory signals.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "bio_factory_synthesis": {
        "description": "Summarize public-safe bio-organic fertilizer batches, input provenance, recipe library, distribution, quality tests, and LAC regional input availability.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "ai_summary_synthesis": {
        "description": "Generate operations, financial, or environmental summary from governed data with registry-backed location check.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": True},
            "summary_type": {"type": "string", "required": False},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "ebf_scorecard_draft": {
        "description": "Draft an EBF scorecard workspace from governed source metrics and evidence links; human review required.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": True},
            "period_start": {"type": "string", "format": "date", "required": True},
            "period_end": {"type": "string", "format": "date", "required": True},
        },
        "outputs": {
            "scorecard": {"type": "object", "required": True},
            "evidence_gaps": {"type": "array", "required": True},
            "safety_note": {"type": "string", "required": True},
        },
        "writes": ["ebf_scorecard:draft", "ebf_score:draft"],
        "high_risk": False,
    },
    "ebf_evidence_gap": {
        "description": "Analyze EBF score evidence gaps by pillar, maturity level, and public readiness.",
        "risk": "low",
        "inputs": {
            "scorecard_id": {"type": "string", "format": "uuid", "required": True},
        },
        "outputs": {
            "evidence_gaps": {"type": "array", "required": True},
            "recommendations": {"type": "array", "required": True},
        },
        "writes": [],
        "high_risk": False,
    },
    "ebf_calibration_memo": {
        "description": "Draft a calibration memo from reviewed scorecards and documented evidence; decisions require human approval.",
        "risk": "medium",
        "inputs": {
            "session_id": {"type": "string", "format": "uuid", "required": True},
        },
        "outputs": {
            "memo": {"type": "object", "required": True},
            "proposed_decisions": {"type": "array", "required": True},
            "safety_note": {"type": "string", "required": True},
        },
        "writes": ["ebf_calibration_decision:draft"],
        "high_risk": False,
    },
    "delphi_facilitation": {
        "description": "Act as the Real-time Delphi facilitator: build an anonymized live summary of panel consensus and draft a recommendation. Agents cannot publish; a human must approve.",
        "risk": "medium",
        "inputs": {
            "study_id": {"type": "string", "format": "uuid", "required": True},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "recommendation_draft": {"type": "object", "required": False},
        },
        "writes": ["delphi_recommendation:draft"],
        "high_risk": False,
    },
    "coordination_strategy_draft": {
        "description": "Draft candidate coordination alliances from stakeholder, capability, market, trust, ecological, and cooperative evidence; human governance is required before any transition.",
        "risk": "medium",
        "inputs": {
            "stakeholder_landscape": {"type": "object", "required": True},
            "capability_gaps": {"type": "array", "required": True},
            "value_stream_bottlenecks": {"type": "array", "required": True},
            "marketplace_evidence": {"type": "object", "required": True},
            "cooperative_evidence": {"type": "object", "required": True},
            "trust_evidence": {"type": "object", "required": True},
            "market_cycle_context": {"type": "object", "required": True},
            "ecological_constraints": {"type": "array", "required": True},
            "stakeholder_constraints": {"type": "array", "required": True},
        },
        "outputs": {
            "candidate_alliance_types": {"type": "array", "required": True},
            "candidate_participants": {"type": "array", "required": True},
            "shared_objective_draft": {"type": "object", "required": True},
            "contribution_assumptions": {"type": "array", "required": True},
            "expected_benefits": {"type": "array", "required": True},
            "risks_and_harms": {"type": "array", "required": True},
            "evidence_gaps": {"type": "array", "required": True},
            "governance_questions": {"type": "array", "required": True},
            "recommended_review_cadence": {"type": "object", "required": True},
        },
        "writes": ["coordination_alliance:draft"],
        "high_risk": False,
    },
    "organic_readiness_synthesis": {
        "description": "Synthesize organic certification readiness, transition progress, input compliance, buffer zone adequacy, harvest segregation, and prohibited substance clearance data.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": True},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
    "ecological_modeling_synthesis": {
        "description": "Synthesize ecological interaction strength, energy flow efficiency, trophic balance, pest trends, soil input retention, biocontrol effectiveness, resource efficiency, conservation status, livestock feed, and reward calibration data.",
        "risk": "medium",
        "inputs": {
            "location_id": {"type": "string", "format": "uuid", "required": True},
            "store": {"type": "boolean", "required": False},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "ai_summary_id": {"type": "string", "format": "uuid", "required": False},
        },
        "writes": ["ai_summary:draft"],
        "high_risk": False,
    },
}

AGENT_TASK_WRITE_CAPABILITIES = frozenset(
    {
        "agent_task:draft",
        "agent_task:submitted",
        "ai_summary:draft",
        "ai_summary:submitted",
        "ebf_calibration_decision:draft",
        "ebf_score:draft",
        "ebf_scorecard:draft",
        "delphi_recommendation:draft",
        "coordination_alliance:draft",
    }
)


def _task_definition(task_key: str) -> dict[str, Any]:
    if task_key not in TASK_CATALOGUE:
        raise KeyError(f"Unknown agent task: {task_key}")
    return TASK_CATALOGUE[task_key]


def validate_task_capabilities(task_key: str) -> None:
    """Fail closed unless every declared task write remains a draft or submission."""
    task = _task_definition(task_key)
    if task.get("high_risk") is not False:
        raise ValueError(f"Agent task {task_key} cannot declare high-risk execution")

    writes = task.get("writes")
    if not isinstance(writes, list):
        raise ValueError(f"Agent task {task_key} must declare writes as a list")

    from services.agents.safety import assess_agent_action

    for target in writes:
        if not isinstance(target, str) or target.count(":") != 1:
            raise ValueError(f"Agent task {task_key} has an invalid write capability")
        collection, status = target.split(":", 1)
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]*", collection)
            or target not in AGENT_TASK_WRITE_CAPABILITIES
        ):
            raise ValueError(f"Agent task {task_key} declares an unapproved write capability")
        if status not in {"draft", "submitted"}:
            raise ValueError(f"Agent task {task_key} may write drafts or submissions only")
        status_field = "review_status" if collection == "agent_task" else "status"
        decision = assess_agent_action("create", collection, {status_field: status})
        if not decision.allowed:
            raise ValueError(f"Agent task {task_key} has a blocked write capability: {decision.reason}")


def list_tasks() -> list[str]:
    """Return supported task keys in stable order."""
    for task_key in TASK_CATALOGUE:
        validate_task_capabilities(task_key)
    return sorted(TASK_CATALOGUE.keys())


def get_task(task_key: str) -> dict[str, Any]:
    """Return one task definition."""
    validate_task_capabilities(task_key)
    return deepcopy(_task_definition(task_key))


def output_schema(task_key: str) -> dict[str, Any]:
    """Return the output schema for a task."""
    return get_task(task_key)["outputs"]


def validate_output(task_key: str, output: dict[str, Any]) -> list[str]:
    """Validate declared top-level output presence, types, and known formats."""
    errors: list[str] = []
    schema = output_schema(task_key)
    for field, spec in schema.items():
        if field not in output:
            if spec.get("required"):
                errors.append(f"Missing required output field: {field}")
            continue

        value = output[field]
        expected_type = spec.get("type")
        type_checks = {
            "array": lambda item: isinstance(item, list),
            "boolean": lambda item: isinstance(item, bool),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "number": lambda item: (
                not isinstance(item, bool)
                and (
                    isinstance(item, int)
                    or (isinstance(item, float) and math.isfinite(item))
                )
            ),
            "object": lambda item: isinstance(item, dict),
            "string": lambda item: isinstance(item, str),
        }
        check_type = type_checks.get(expected_type)
        if check_type is None:
            errors.append(f"Unsupported output schema type for field: {field}")
            continue
        if not check_type(value):
            errors.append(f"Invalid output type for field: {field} (expected {expected_type})")
            continue

        output_format = spec.get("format")
        if output_format == "uuid":
            try:
                UUID(value)
            except (TypeError, ValueError, AttributeError):
                errors.append(f"Invalid output format for field: {field} (expected uuid)")
        elif output_format is not None:
            errors.append(f"Unsupported output format for field: {field}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut agent task catalogue")
    parser.add_argument("--list", action="store_true", help="List task keys")
    parser.add_argument("--describe", help="Print one task definition")
    args = parser.parse_args()

    if args.list:
        print("\n".join(list_tasks()))
        return

    if args.describe:
        print(json.dumps(get_task(args.describe), indent=2, sort_keys=True))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
