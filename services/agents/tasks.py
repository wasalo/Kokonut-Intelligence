"""Agent task catalogue and output schema helpers."""

from __future__ import annotations

import argparse
import json
from typing import Any

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
}


def list_tasks() -> list[str]:
    """Return supported task keys in stable order."""
    return sorted(TASK_CATALOGUE.keys())


def get_task(task_key: str) -> dict[str, Any]:
    """Return one task definition."""
    if task_key not in TASK_CATALOGUE:
        raise KeyError(f"Unknown agent task: {task_key}")
    return TASK_CATALOGUE[task_key]


def output_schema(task_key: str) -> dict[str, Any]:
    """Return the output schema for a task."""
    return get_task(task_key)["outputs"]


def validate_output(task_key: str, output: dict[str, Any]) -> list[str]:
    """Perform lightweight required-field output validation."""
    errors: list[str] = []
    schema = output_schema(task_key)
    for field, spec in schema.items():
        if spec.get("required") and field not in output:
            errors.append(f"Missing required output field: {field}")
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
