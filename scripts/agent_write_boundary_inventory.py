#!/usr/bin/env python3
"""Inventory legacy and authenticated AI-summary draft write boundaries.

The inventory records source locations and statement classifications only. It
does not persist SQL text, data values, credentials, or runtime database state.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

AI_SUMMARY_INSERT = re.compile(r"^\s*INSERT\s+INTO\s+(?:public\.)?ai_summary\b", re.IGNORECASE)
AUTHENTICATED_DRAFT_CALL = re.compile(
    r"\bkokonut_security\.create_location_ai_summary_draft\s*\(", re.IGNORECASE
)


def _sql_text(node: ast.AST) -> str:
    """Return static string portions of a query expression for classification."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value
            for value in node.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    if isinstance(node, ast.Call) and node.args:
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"text", "SQL"}:
            return _sql_text(node.args[0])
        if isinstance(node.func, ast.Name) and node.func.id in {"text", "SQL"}:
            return _sql_text(node.args[0])
    return ""


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def build_inventory(root: Path = ROOT) -> dict:
    """Classify direct legacy writes and the authenticated Gateway draft path."""
    legacy_writes: list[dict] = []
    authenticated_calls: list[dict] = []
    legacy_context_calls: list[dict] = []

    for package in ("services",):
        package_path = root / package
        if not package_path.exists():
            continue
        for path in sorted(package_path.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, SyntaxError) as exc:
                raise ValueError(f"Unable to parse agent write source {relative}") from exc

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = _call_name(node.func)
                if name == "set_agent_context":
                    legacy_context_calls.append({"source": relative, "line": node.lineno})

                if name == "execute" and node.args:
                    query = _sql_text(node.args[0])
                    if relative.startswith("services/agents/") and AI_SUMMARY_INSERT.search(query):
                        legacy_writes.append({"source": relative, "line": node.lineno})
                    if relative.startswith("services/gateway/") and AUTHENTICATED_DRAFT_CALL.search(query):
                        authenticated_calls.append({"source": relative, "line": node.lineno})

    legacy_writes.sort(key=lambda item: (item["source"], item["line"]))
    authenticated_calls.sort(key=lambda item: (item["source"], item["line"]))
    legacy_context_calls.sort(key=lambda item: (item["source"], item["line"]))
    return {
        "version": 1,
        "generated_by": "scripts/agent_write_boundary_inventory.py",
        "scope": (
            "Static Python call-site inventory for direct AI-summary inserts in services/agents, "
            "the signed operator draft function call in services/gateway, and calls to the "
            "disabled set_agent_context helper. Source locations classify code paths; they do "
            "not prove runtime identity, database privileges, query reachability, or tenant isolation."
        ),
        "summary": {
            "legacy_direct_ai_summary_insert_sites": len(legacy_writes),
            "authenticated_operator_draft_function_calls": len(authenticated_calls),
            "set_agent_context_call_sites": len(legacy_context_calls),
        },
        "legacy_direct_ai_summary_inserts": legacy_writes,
        "authenticated_operator_draft_function_calls": authenticated_calls,
        "set_agent_context_call_sites": legacy_context_calls,
    }


def serialize(inventory: dict) -> str:
    return json.dumps(inventory, indent=2, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated inventory")
    group.add_argument("--check", type=Path, help="Fail if the saved inventory is stale")
    args = parser.parse_args(argv)
    expected = serialize(build_inventory())

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        print(f"Wrote agent write-boundary inventory: {output.relative_to(ROOT)}")
        return 0

    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing agent write-boundary inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Agent write-boundary inventory is stale: {check}", file=sys.stderr)
        return 1
    print(f"Agent write-boundary inventory is current: {check.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
