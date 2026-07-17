"""Deterministic StratML Part 1 projection for governed strategy plans.

PostgreSQL remains canonical. This module only projects approved strategy data
into the ISO 17469-1 core vocabulary for exchange and publication.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from xml.etree import ElementTree as ET

from services.ingestion.base import get_db
from .ids import xml_id

STRATML_NS = "urn:ISO:std:iso:17469:tech:xsd:stratml_core"
ET.register_namespace("", STRATML_NS)


class StratMLExportError(ValueError):
    """Raised when a strategy cannot be safely projected to StratML."""


def _tag(name: str) -> str:
    return f"{{{STRATML_NS}}}{name}"


def _text(parent: ET.Element, name: str, value: Any) -> ET.Element:
    element = ET.SubElement(parent, _tag(name))
    element.text = "" if value is None else str(value)
    return element


def _date_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _identifier(prefix: str, value: Any) -> str:
    return xml_id(prefix, value)


def _require_plan(plan: Mapping[str, Any], allow_draft: bool) -> None:
    plan_id = plan.get("id")
    if not plan_id:
        raise StratMLExportError("strategy plan is missing id")
    if not str(plan.get("name", "")).strip():
        raise StratMLExportError("strategy plan is missing name")
    if plan.get("planning_horizon_end") < plan.get("planning_horizon_start"):
        raise StratMLExportError("strategy plan horizon is invalid")
    if not allow_draft and plan.get("status") not in ("approved", "active"):
        raise StratMLExportError(
            "only approved or active strategy plans may be exported; "
            "pass allow_draft=True for internal review"
        )


def build_stratml_document(
    plan: Mapping[str, Any],
    entries: Iterable[Mapping[str, Any]],
    statements: Iterable[Mapping[str, Any]] = (),
    *,
    source_url: Optional[str] = None,
    export_date: Optional[Any] = None,
    allow_draft: bool = False,
) -> ET.ElementTree:
    """Build a deterministic StratML Part 1 document from relational rows."""
    _require_plan(plan, allow_draft)

    root = ET.Element(_tag("StrategicPlan"))
    _text(root, "Name", plan["name"])
    description = plan.get("diagnosis_summary") or plan.get("guiding_policy")
    if description:
        _text(root, "Description", description)
    other = []
    if plan.get("guiding_policy"):
        other.append(f"Guiding policy: {plan['guiding_policy']}")
    if plan.get("theory_of_change"):
        other.append(f"Theory of change: {plan['theory_of_change']}")
    if plan.get("uncertainty_summary"):
        other.append(f"Uncertainty: {plan['uncertainty_summary']}")
    if other:
        _text(root, "OtherInformation", "\n".join(other))

    core = ET.SubElement(root, _tag("StrategicPlanCore"))
    statements_by_type = {row.get("statement_type"): row for row in statements}
    vision = statements_by_type.get("vision")
    if vision:
        element = ET.SubElement(core, _tag("Vision"))
        _text(element, "Description", vision.get("statement_text"))
        _text(element, "Identifier", _identifier("vision", vision.get("id")))
    mission = statements_by_type.get("mission")
    if mission:
        element = ET.SubElement(core, _tag("Mission"))
        _text(element, "Description", mission.get("statement_text"))
        _text(element, "Identifier", _identifier("mission", mission.get("id")))
    for value in sorted(
        (row for row in statements if row.get("statement_type") == "values"),
        key=lambda row: (str(row.get("statement_text", "")), str(row.get("id", ""))),
    ):
        element = ET.SubElement(core, _tag("Value"))
        _text(element, "Name", value.get("statement_text"))
        _text(element, "Identifier", _identifier("value", value.get("id")))

    grouped: "OrderedDict[str, list[Mapping[str, Any]]]" = OrderedDict()
    for entry in sorted(
        entries,
        key=lambda row: (
            str(row.get("strategic_theme") or row.get("perspective") or "General"),
            str(row.get("perspective") or ""),
            str(row.get("statement") or ""),
            str(row.get("id") or ""),
        ),
    ):
        group_name = str(entry.get("strategic_theme") or entry.get("perspective") or "General")
        grouped.setdefault(group_name, []).append(entry)

    for sequence, (group_name, group_entries) in enumerate(grouped.items(), start=1):
        goal = ET.SubElement(core, _tag("Goal"))
        _text(goal, "Name", group_name)
        _text(goal, "Description", f"Strategic objectives in the {group_name} theme.")
        _text(goal, "Identifier", _identifier("goal", f"{plan['id']}-{sequence}"))
        _text(goal, "SequenceIndicator", sequence)
        for objective_sequence, entry in enumerate(group_entries, start=1):
            objective = ET.SubElement(goal, _tag("Objective"))
            _text(objective, "Name", entry.get("statement"))
            details = []
            if entry.get("perspective"):
                details.append(f"Perspective: {entry['perspective']}")
            if entry.get("unit") and entry.get("target_value") is not None:
                details.append(f"Target: {entry['target_value']} {entry['unit']}")
            if entry.get("current_value") is not None:
                details.append(f"Current: {entry['current_value']}")
            if entry.get("status"):
                details.append(f"Status: {entry['status']}")
            if details:
                _text(objective, "Description", "; ".join(details))
            _text(objective, "Identifier", _identifier("objective", entry.get("id")))
            _text(objective, "SequenceIndicator", objective_sequence)

    admin = ET.SubElement(root, _tag("AdministrativeInformation"))
    _text(admin, "StartDate", _date_text(plan.get("planning_horizon_start")))
    _text(admin, "EndDate", _date_text(plan.get("planning_horizon_end")))
    publication = _date_text(export_date or plan.get("approved_at") or datetime.now(timezone.utc))
    _text(admin, "PublicationDate", publication)
    if source_url:
        _text(admin, "Source", source_url)
    return ET.ElementTree(root)


def _fetch_rows(conn, plan_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
        plan_row = cur.fetchone()
        if not plan_row:
            raise StratMLExportError(f"strategy plan not found: {plan_id}")
        plan = dict(plan_row)
        cur.execute(
            "SELECT * FROM strategy_map WHERE strategy_plan_id = %s::uuid "
            "ORDER BY strategic_theme NULLS LAST, perspective, statement, id",
            (plan_id,),
        )
        entries = [dict(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT * FROM vision_mission WHERE entity_type = %s AND "
            "(entity_id = %s::uuid OR entity_id IS NULL) AND status = 'approved' "
            "ORDER BY statement_type, effective_date DESC, id",
            (plan["scope_type"], plan["scope_id"]),
        )
        statements = [dict(row) for row in cur.fetchall()]
    return plan, entries, statements


def export_strategy_plan(
    conn,
    plan_id: str,
    *,
    output: Optional[str] = None,
    source_url: Optional[str] = None,
    allow_draft: bool = False,
) -> str:
    """Export one strategy plan and optionally write it to a file."""
    plan, entries, statements = _fetch_rows(conn, plan_id)
    document = build_stratml_document(
        plan,
        entries,
        statements,
        source_url=source_url,
        allow_draft=allow_draft,
    )
    payload = ET.tostring(document.getroot(), encoding="utf-8", xml_declaration=True).decode()
    if output:
        Path(output).write_text(payload + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a governed strategy plan as StratML Part 1 XML")
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--output")
    parser.add_argument("--source-url")
    parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    conn = get_db()
    try:
        payload = export_strategy_plan(
            conn,
            args.plan_id,
            output=args.output,
            source_url=args.source_url,
            allow_draft=args.allow_draft,
        )
        if not args.output:
            print(payload)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
