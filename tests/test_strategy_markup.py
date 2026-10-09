"""Focused tests for the StratML Part 1 strategy projection."""

from datetime import date
from xml.etree import ElementTree as ET

import pytest

from services.strategy_markup.exporter import (
    STRATML_NS,
    StratMLExportError,
    build_stratml_document,
)
from services.strategy_markup.ids import stable_id, xml_id
from services.strategy_markup.mapping import normalize_strategy
from services.strategy_markup.validator import validate_strategy, validate_xml_document


def _plan(status="approved"):
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Adelphi Strategy",
        "status": status,
        "planning_horizon_start": date(2026, 1, 1),
        "planning_horizon_end": date(2028, 12, 31),
        "diagnosis_summary": "Coordination is the primary constraint.",
        "guiding_policy": "Build governed local capability.",
        "theory_of_change": "Capability enables durable outcomes.",
        "uncertainty_summary": "Climate variability remains material.",
        "approved_at": date(2026, 1, 15),
    }


def _entries():
    return [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "perspective": "customer",
            "strategic_theme": "Community resilience",
            "statement": "Improve local food access",
            "target_value": 80,
            "current_value": 40,
            "unit": "percent",
            "status": "on_track",
        },
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "perspective": "learning_growth",
            "strategic_theme": "Capability",
            "statement": "Develop farmer training",
            "target_value": 12,
            "current_value": 3,
            "unit": "sessions",
            "status": "behind",
        },
    ]


def test_builds_deterministic_stratml_core_document():
    statements = [
        {"id": "v1", "statement_type": "vision", "statement_text": "Thriving farms."},
        {"id": "m1", "statement_type": "mission", "statement_text": "Coordinate regenerative agriculture."},
        {"id": "val2", "statement_type": "values", "statement_text": "Stewardship"},
        {"id": "val1", "statement_type": "values", "statement_text": "Transparency"},
    ]
    first = ET.tostring(
        build_stratml_document(_plan(), _entries(), statements, export_date=date(2026, 2, 1)).getroot(),
        encoding="unicode",
    )
    second = ET.tostring(
        build_stratml_document(_plan(), list(reversed(_entries())), list(reversed(statements)), export_date=date(2026, 2, 1)).getroot(),
        encoding="unicode",
    )

    assert first == second
    root = ET.fromstring(first)
    assert root.tag == f"{{{STRATML_NS}}}StrategicPlan"
    assert root.find(f"{{{STRATML_NS}}}StrategicPlanCore/{{{STRATML_NS}}}Mission") is not None
    assert len(root.findall(f".//{{{STRATML_NS}}}Goal")) == 2
    assert len(root.findall(f".//{{{STRATML_NS}}}Objective")) == 2
    assert "2026-02-01" in first


def test_draft_plan_requires_explicit_internal_export_flag():
    with pytest.raises(StratMLExportError, match="approved or active"):
        build_stratml_document(_plan(status="draft"), _entries())

    document = build_stratml_document(_plan(status="draft"), _entries(), allow_draft=True)
    assert document.getroot().tag == f"{{{STRATML_NS}}}StrategicPlan"


def test_invalid_horizon_is_rejected():
    plan = _plan()
    plan["planning_horizon_end"] = date(2025, 12, 31)
    with pytest.raises(StratMLExportError, match="horizon"):
        build_stratml_document(plan, _entries())


def test_identifiers_are_stable_and_xml_safe():
    assert stable_id("objective", "same") == stable_id("objective", "same")
    assert xml_id("objective", "same").startswith("objective-")
    assert " " not in xml_id("objective", "same value")


def test_normalized_strategy_validates_references_and_governance():
    plan = _plan()
    document = normalize_strategy(plan, _entries(), indicators=[
        {"id": "indicator-1", "name": "Food access", "objective_id": _entries()[0]["id"], "review_status": "verified"}
    ])
    assert validate_strategy(document) == []
    draft = normalize_strategy({**plan, "status": "draft"}, _entries())
    assert "public strategy projections" in validate_strategy(draft)[0]
    assert validate_strategy(draft, allow_draft=True) == []


def test_xml_validator_checks_minimum_structure():
    payload = ET.tostring(build_stratml_document(_plan(), _entries()).getroot(), encoding="unicode")
    assert validate_xml_document(payload) == []
    assert validate_xml_document("<not-a-strategy />") == ["root element must be StrategicPlan"]
