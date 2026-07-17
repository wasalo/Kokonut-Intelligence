"""Semantic and structural validation for normalized strategy documents."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from .model import StrategyDocument


ALLOWED_CHAIN_TYPES = {"input", "process", "output", "outcome", "stakeholder_result"}


def validate_strategy(document: StrategyDocument, *, allow_draft: bool = False) -> list[str]:
    """Return deterministic validation findings; an empty list means valid."""
    findings: list[str] = []
    if not document.name.strip():
        findings.append("strategy name is required")
    if document.horizon_end < document.horizon_start:
        findings.append("strategy horizon end precedes start")
    if not allow_draft and document.status not in {"approved", "active"}:
        findings.append("public strategy projections require approved or active status")
    ids = [document.id]
    ids.extend(statement.id for statement in document.statements)
    ids.extend(goal.id for goal in document.goals)
    ids.extend(objective.id for goal in document.goals for objective in goal.objectives)
    ids.extend(indicator.id for indicator in document.indicators)
    ids.extend(link.id for link in document.value_chain)
    if len(ids) != len(set(ids)):
        findings.append("strategy projection contains duplicate identifiers")
    indicator_ids = {indicator.id for indicator in document.indicators}
    objective_ids = {objective.id for goal in document.goals for objective in goal.objectives}
    for indicator in document.indicators:
        if indicator.objective_id and indicator.objective_id not in objective_ids:
            findings.append(f"indicator {indicator.id} references an unknown objective")
        if indicator.period_start and indicator.period_end and indicator.period_end < indicator.period_start:
            findings.append(f"indicator {indicator.id} has an invalid reporting period")
    for link in document.value_chain:
        if link.value_chain_type not in ALLOWED_CHAIN_TYPES:
            findings.append(f"value-chain link {link.id} has an invalid type")
        if link.performance_indicator_id and link.performance_indicator_id not in indicator_ids:
            findings.append(f"value-chain link {link.id} references an unknown indicator")
    return findings


def validate_xml_document(payload: str) -> list[str]:
    """Validate the minimum StratML Part 1/2 structural contract."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        return [f"invalid XML: {exc}"]
    if not root.tag.endswith("StrategicPlan"):
        return ["root element must be StrategicPlan"]
    ns = root.tag.split("}", 1)[0] + "}" if root.tag.startswith("{") else ""
    findings = []
    if root.find(f"{ns}Name") is None:
        findings.append("StrategicPlan.Name is required")
    if root.find(f"{ns}StrategicPlanCore") is None:
        findings.append("StrategicPlanCore is required")
    for objective in root.findall(f".//{ns}Objective"):
        if objective.find(f"{ns}Identifier") is None:
            findings.append("every Objective requires an Identifier")
    return findings


def assert_valid(document: StrategyDocument, *, allow_draft: bool = False) -> None:
    findings = validate_strategy(document, allow_draft=allow_draft)
    if findings:
        raise ValueError("; ".join(findings))
