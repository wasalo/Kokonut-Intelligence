"""Agent task catalogue and output schema helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from services.registry.cids_contract import CIDS_ALIGNMENT_TIER, CIDS_VERSION

CIDS_SOURCE_VIEWS = (
    "kokonut_agent_source.cids_location",
    "kokonut_agent_source.cids_stakeholder_outcome",
    "kokonut_agent_source.cids_farm_impact_mapping",
    "kokonut_agent_source.cids_metric_value",
    "kokonut_agent_source.cids_stakeholder_feedback",
    "kokonut_agent_source.cids_impact_claim",
)
_CIDS_SOURCE_RECORD_ID = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")
_CIDS_ARTIFACT_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def cids_artifact_sha256(
    document: dict[str, Any], property_source_records: list[dict[str, Any]]
) -> str:
    """Hash the canonical exported JSON-LD document and its row-lineage sidecar."""

    def json_default(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    canonical = json.dumps(
        {
            "document": document,
            "property_source_records": property_source_records,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=json_default,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

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
            "source_scope": {"type": "object", "required": True},
        },
        "writes": [],
        "high_risk": False,
    },
    "feedback_synthesis": {
        "description": "Summarize stakeholder feedback from consented public summaries only.",
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
    "capital_efficiency_synthesis": {
        "description": "Summarize public-safe capital efficiency, regenerative payback, governance throughput, and capital-provider utility scenarios.",
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
    "commons_liberation_synthesis": {
        "description": "Summarize public-safe time liberation, capital alignment, governance inclusion, and land stewardship evidence.",
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
    "gnh_alignment_synthesis": {
        "description": "Summarize public-safe GNH alignment, cultural preservation, renewable energy, vulnerable access, and foundational well-being evidence.",
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
    "regenerator_synthesis": {
        "description": "Summarize public-safe regenerative outcomes, community governance, replication readiness, and adaptive stewardship evidence.",
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
    "open_source_capitalist_synthesis": {
        "description": "Summarize public-safe scaling economics, adoption barriers, perpetual-value stress tests, and open-source reuse evidence.",
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
    "kokonut_commons_synthesis": {
        "description": "Summarize public-safe anti-capture governance, flexible redistribution policies, federation protocols, algorithmic redistribution mechanisms, and participatory signals.",
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
    "bio_factory_synthesis": {
        "description": "Summarize public-safe bio-organic fertilizer batches, input provenance, recipe library, distribution, quality tests, and LAC regional input availability.",
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
            "location_id": {"type": "string", "format": "uuid", "required": True},
        },
        "outputs": {
            "evidence_gaps": {"type": "array", "required": True},
            "recommendations": {"type": "array", "required": True},
            "source_scope": {"type": "object", "required": True},
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
        "description": "Act as the Real-time Delphi facilitator: build a consent-aware, location-scoped live summary and an in-memory recommendation suggestion. Persistence and review require the authenticated operator Gateway.",
        "risk": "medium",
        "inputs": {
            "study_id": {"type": "string", "format": "uuid", "required": True},
            "location_id": {"type": "string", "format": "uuid", "required": True},
        },
        "outputs": {
            "summary": {"type": "object", "required": True},
            "recommendation_draft": {"type": "object", "required": False},
        },
        "writes": [],
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
    """Validate task schemas and fail closed unless writes stay draft/submission only."""
    task = _task_definition(task_key)
    if task.get("high_risk") is not False:
        raise ValueError(f"Agent task {task_key} cannot declare high-risk execution")

    supported_schema_keys = {"type", "format", "required"}
    for section in ("inputs", "outputs"):
        schema = task.get(section)
        if not isinstance(schema, dict):
            raise ValueError(f"Agent task {task_key} must declare {section} as an object")
        for field, spec in schema.items():
            if not isinstance(field, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", field):
                raise ValueError(f"Agent task {task_key} has an invalid {section} field name")
            if not isinstance(spec, dict):
                raise ValueError(f"Agent task {task_key} has an invalid {section} schema for {field}")
            if set(spec) - supported_schema_keys:
                raise ValueError(f"Agent task {task_key} uses unsupported {section} schema constraints for {field}")
            expected_type = spec.get("type")
            if not isinstance(expected_type, str) or expected_type not in _SCHEMA_TYPE_CHECKS:
                raise ValueError(f"Agent task {task_key} uses unsupported {section} schema type for {field}")
            if not isinstance(spec.get("required"), bool):
                raise ValueError(f"Agent task {task_key} has an invalid {section} required flag for {field}")
            value_format = spec.get("format")
            if value_format is not None:
                if (
                    not isinstance(value_format, str)
                    or value_format not in {"uuid", "date"}
                    or expected_type != "string"
                ):
                    raise ValueError(f"Agent task {task_key} uses unsupported {section} format for {field}")

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


_SCHEMA_TYPE_CHECKS = {
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


def _validate_declared_fields(
    schema: dict[str, Any], values: dict[str, Any], *, field_kind: str
) -> list[str]:
    if not isinstance(values, dict):
        return [f"{field_kind.capitalize()} values must be an object"]

    errors: list[str] = []
    for field, spec in schema.items():
        if field not in values:
            if spec.get("required"):
                if field_kind == "output":
                    errors.append(f"Missing required output field: {field}")
                else:
                    errors.append(f"Missing required task input: {field}")
            continue

        value = values[field]
        expected_type = spec.get("type")
        check_type = _SCHEMA_TYPE_CHECKS.get(expected_type)
        if check_type is None:
            errors.append(f"Unsupported {field_kind} schema type for field: {field}")
            continue
        if not check_type(value):
            errors.append(
                f"Invalid {field_kind} type for field: {field} (expected {expected_type})"
            )
            continue

        value_format = spec.get("format")
        if value_format in {"uuid", "date"}:
            try:
                if value_format == "uuid":
                    UUID(value)
                else:
                    parsed_date = date.fromisoformat(value)
                    if parsed_date.isoformat() != value:
                        raise ValueError("date must use YYYY-MM-DD")
            except (TypeError, ValueError, AttributeError):
                errors.append(
                    f"Invalid {field_kind} format for field: {field} (expected {value_format})"
                )
        elif value_format is not None:
            errors.append(f"Unsupported {field_kind} format for field: {field}")
    return errors


def validate_task_inputs(task_key: str, inputs: dict[str, Any]) -> list[str]:
    """Validate declared top-level task input presence, types, and formats."""
    return _validate_declared_fields(
        get_task(task_key)["inputs"], inputs, field_kind="task input"
    )


def validate_output(task_key: str, output: dict[str, Any]) -> list[str]:
    """Validate declared outputs and task-specific nested contracts."""
    errors = _validate_declared_fields(
        output_schema(task_key), output, field_kind="output"
    )
    if task_key == "cids_export":
        document = output.get("document") if isinstance(output, dict) else None
        source_scope = output.get("source_scope") if isinstance(output, dict) else None
        if isinstance(source_scope, dict):
            if set(source_scope) != {
                "location_id",
                "views",
                "property_source_records",
                "artifact_sha256",
            }:
                errors.append("Invalid CIDS source scope fields")
            location_id = source_scope.get("location_id")
            try:
                normalized_location_id = str(UUID(str(location_id)))
            except (TypeError, ValueError, AttributeError):
                normalized_location_id = None
            if normalized_location_id is None or normalized_location_id != location_id:
                errors.append("Invalid CIDS source scope location identifier")
            if source_scope.get("views") != list(CIDS_SOURCE_VIEWS):
                errors.append("Invalid CIDS source scope views")
        if isinstance(document, dict):
            graph = document.get("@graph")
            if not isinstance(graph, list):
                errors.append("Invalid CIDS document graph (expected array)")
            else:
                if not graph:
                    errors.append("Invalid CIDS document graph (expected nodes)")
                graph_count = output.get("graph_count")
                if (
                    not isinstance(graph_count, int)
                    or isinstance(graph_count, bool)
                    or graph_count != len(graph)
                ):
                    errors.append("Invalid CIDS graph count")
                if output.get("alignment_tier") != document.get("kokonut:alignmentTier"):
                    errors.append("Invalid CIDS alignment tier")
                if document.get("kokonut:alignmentTier") != CIDS_ALIGNMENT_TIER:
                    errors.append("Unsupported CIDS alignment tier")
                if output.get("cids_version") != document.get("kokonut:cidsVersion"):
                    errors.append("Invalid CIDS version")
                if document.get("kokonut:cidsVersion") != CIDS_VERSION:
                    errors.append("Unsupported CIDS version")
                if any(
                    not isinstance(node, dict)
                    or not isinstance(node.get("@id"), str)
                    or not node["@id"].strip()
                    or not isinstance(node.get("kokonut:sourceViews"), list)
                    or not node["kokonut:sourceViews"]
                    or any(
                        not isinstance(view, str) or not view.strip()
                        for view in node["kokonut:sourceViews"]
                    )
                    or node["kokonut:sourceViews"]
                    != sorted(set(node["kokonut:sourceViews"]))
                    or not set(node["kokonut:sourceViews"]).issubset(CIDS_SOURCE_VIEWS)
                    for node in graph
                ):
                    errors.append(
                        "Invalid CIDS document graph node source-view provenance"
                    )
                elif any(
                    not isinstance(node.get("kokonut:propertySourceViews"), dict)
                    or set(node["kokonut:propertySourceViews"])
                    != set(node)
                    - {
                        "@context",
                        "@type",
                        "kokonut:sourceViews",
                        "kokonut:propertySourceViews",
                    }
                    or any(
                        not isinstance(views, list)
                        or any(
                            not isinstance(view, str)
                            or not view.strip()
                            or view not in CIDS_SOURCE_VIEWS
                            for view in views
                        )
                        or views != sorted(set(views))
                        for views in node["kokonut:propertySourceViews"].values()
                    )
                    for node in graph
                ):
                    errors.append(
                        "Invalid CIDS document graph node property-source provenance"
                    )
            property_records = (
                source_scope.get("property_source_records")
                if isinstance(source_scope, dict)
                else None
            )
            if (
                not isinstance(graph, list)
                or not isinstance(property_records, list)
                or len(property_records) != len(graph)
            ):
                errors.append("Invalid CIDS property-to-row lineage coverage")
            else:
                for node_index, (node, lineage) in enumerate(zip(graph, property_records)):
                    expected_properties = (
                        node.get("kokonut:propertySourceViews")
                        if isinstance(node, dict)
                        else None
                    )
                    if (
                        not isinstance(expected_properties, dict)
                        or not isinstance(lineage, dict)
                        or set(lineage) != {"node_index", "node_id", "properties"}
                        or isinstance(lineage.get("node_index"), bool)
                        or lineage.get("node_index") != node_index
                        or lineage.get("node_id") != node.get("@id")
                        or not isinstance(lineage.get("properties"), list)
                    ):
                        errors.append("Invalid CIDS property-to-row lineage node")
                        continue
                    property_lineage = lineage["properties"]
                    property_names = [
                        item.get("property") if isinstance(item, dict) else None
                        for item in property_lineage
                    ]
                    if property_names != sorted(expected_properties) or any(
                        not isinstance(item, dict)
                        or set(item) != {"property", "row_count", "records", "truncated"}
                        for item in property_lineage
                    ):
                        errors.append("Invalid CIDS property-to-row lineage properties")
                        continue
                    for item in property_lineage:
                        row_count = item.get("row_count")
                        records = item.get("records")
                        truncated = item.get("truncated")
                        allowed_property_views = expected_properties[item["property"]]
                        if (
                            not isinstance(row_count, int)
                            or isinstance(row_count, bool)
                            or row_count < 0
                            or not isinstance(records, list)
                            or len(records) > 50
                            or not isinstance(truncated, bool)
                            or len(records) != min(row_count, 50)
                            or (bool(allowed_property_views) and row_count == 0)
                            or truncated != (row_count > len(records))
                        ):
                            errors.append("Invalid CIDS property-to-row lineage record count")
                            break
                        record_keys = []
                        for record in records:
                            if (
                                not isinstance(record, dict)
                                or set(record) != {"view", "record_id"}
                                or record.get("view") not in allowed_property_views
                                or record.get("view") not in CIDS_SOURCE_VIEWS
                                or not isinstance(record.get("record_id"), str)
                                or _CIDS_SOURCE_RECORD_ID.fullmatch(record["record_id"]) is None
                            ):
                                errors.append("Invalid CIDS property-to-row lineage record")
                                break
                            record_keys.append((record["view"], record["record_id"]))
                        if record_keys != sorted(set(record_keys)):
                            errors.append("Invalid CIDS property-to-row lineage ordering")
                            break
            artifact_digest = source_scope.get("artifact_sha256")
            if (
                not isinstance(artifact_digest, str)
                or _CIDS_ARTIFACT_DIGEST.fullmatch(artifact_digest) is None
            ):
                errors.append("Invalid CIDS artifact digest")
            elif isinstance(document, dict) and isinstance(property_records, list):
                try:
                    expected_digest = cids_artifact_sha256(document, property_records)
                except (TypeError, ValueError):
                    expected_digest = None
                if artifact_digest != expected_digest:
                    errors.append("Invalid CIDS artifact digest")
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
