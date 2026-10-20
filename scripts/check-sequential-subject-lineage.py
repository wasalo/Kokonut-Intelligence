#!/usr/bin/env python3
"""Audit source-level subject lineage for the CAP-036 read projection.

This is a repository source audit only. It does not connect to PostgreSQL and
cannot describe a populated or archived database corpus.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = {
    "summary": ROOT / "schemas/postgres/460_location_scoped_sequential_decision_summary.sql",
    "timeline": ROOT / "schemas/postgres/478_location_sequential_evidence_timeline.sql",
}
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-036-subject-lineage-source-audit.json"
EXPECTED_LINEAGES = {"strategy_plan", "threat", "solution"}
INSERT_RE = re.compile(r"\binsert\s+into\s+(?:public\.)?decision_hypothesis\b", re.IGNORECASE)
SUBJECT_RE = re.compile(r"hypothesis\.subject_type\s*=\s*'([^']+)'", re.IGNORECASE)


def _module_import_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    function_aliases = {"create_hypothesis"}
    module_aliases = {"sequential_evidence"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("sequential_evidence"):
            for alias in node.names:
                if alias.name == "create_hypothesis":
                    function_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith("sequential_evidence"):
                    module_aliases.add(alias.asname or alias.name.rsplit(".", 1)[-1])
    return function_aliases, module_aliases


def _generic_hypothesis_calls(paths: list[Path]) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        function_aliases, module_aliases = _module_import_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            is_generic = (
                isinstance(function, ast.Name) and function.id in function_aliases
            ) or (
                isinstance(function, ast.Attribute)
                and function.attr == "create_hypothesis"
                and isinstance(function.value, ast.Name)
                and function.value.id in module_aliases
            )
            if is_generic:
                calls.append({"file": path.relative_to(ROOT).as_posix(), "line": node.lineno})
    return calls


def _test_subject_types(paths: list[Path]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        _function_aliases, module_aliases = _module_import_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "create_hypothesis" or not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id not in module_aliases or not node.args:
                continue
            # sequential_evidence.create_hypothesis(conn, subject_type, ...)
            value = node.args[1] if len(node.args) > 1 else None
            found.append({
                "file": path.relative_to(ROOT).as_posix(),
                "line": node.lineno,
                "subject_type": value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else "dynamic-or-fixture",
            })
    return found


def _assert_lineage_contract(name: str, sql: str) -> list[str]:
    actual = set(SUBJECT_RE.findall(sql))
    if actual != EXPECTED_LINEAGES:
        raise ValueError(f"{name} subject allowlist differs: expected {sorted(EXPECTED_LINEAGES)}, found {sorted(actual)}")

    required_fragments = {
        "strategy_plan": (
            "FROM public.strategy_plan AS plan",
            "plan.id = hypothesis.subject_id",
            "plan.scope_type = 'location'",
            "plan.scope_id = requested_location_id",
        ),
        "threat": (
            "FROM public.threat AS item",
            "item.id = hypothesis.subject_id",
            "item.location_id = requested_location_id",
        ),
        "solution": (
            "FROM public.solution AS item",
            "item.id = hypothesis.subject_id",
            "item.originating_scope_id = requested_location_id",
            "FROM public.solution_link AS location_link",
            "location_link.entity_type = 'location'",
            "location_link.entity_id = requested_location_id",
        ),
    }
    for subject_type, fragments in required_fragments.items():
        for fragment in fragments:
            if fragment not in sql:
                raise ValueError(f"{name} {subject_type} lineage is missing scope fragment: {fragment}")
    return sorted(actual)


def build_inventory() -> dict[str, object]:
    service_paths = sorted((ROOT / "services").rglob("*.py"))
    test_paths = sorted((ROOT / "tests").rglob("*.py"))
    writer = ROOT / "services/decision/sequential_evidence.py"
    direct_inserts = [
        path.relative_to(ROOT).as_posix()
        for path in service_paths
        if INSERT_RE.search(path.read_text(encoding="utf-8"))
    ]
    expected_writer = [writer.relative_to(ROOT).as_posix()]
    if direct_inserts != expected_writer:
        raise ValueError(f"unexpected service SQL writer(s): {direct_inserts}")

    production_calls = [call for call in _generic_hypothesis_calls(service_paths) if call["file"] != expected_writer[0]]
    if production_calls:
        raise ValueError(f"generic sequential-hypothesis production caller(s) need lineage review: {production_calls}")

    migration_lineages = {}
    for name, path in MIGRATIONS.items():
        migration_lineages[name] = _assert_lineage_contract(
            name, path.read_text(encoding="utf-8")
        )
    if migration_lineages["summary"] != migration_lineages["timeline"]:
        raise ValueError("summary and timeline lineage allowlists drifted")

    customer_value = (ROOT / "services/analytics/customer_value.py").read_text(encoding="utf-8")
    if "INSERT INTO strategy_customer_value_hypothesis" not in customer_value:
        raise ValueError("customer-value hypothesis write target changed; review CAP-036 lineage inventory")
    if "INSERT INTO decision_hypothesis" in customer_value:
        raise ValueError("customer-value hypotheses now write to the sequential decision ledger")

    return {
        "result": "passed",
        "audit_type": "repository source audit; no database access",
        "database_corpus_inspected": False,
        "sequential_ledger_sql_writers": direct_inserts,
        "production_call_sites_of_generic_writer": production_calls,
        "projection_lineages": migration_lineages["summary"],
        "projection_lineages_match_across_summary_and_timeline": True,
        "test_fixture_subject_types": _test_subject_types(test_paths),
        "separate_customer_value_hypothesis_table": "strategy_customer_value_hypothesis",
        "decision": (
            "Keep unknown subject types excluded. Repository code has no production call site beyond the generic writer, "
            "which accepts arbitrary subject types. Populated/archived corpus lineage requires a database-backed inventory "
            "before any additional subject type can be exposed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="validate the source inventory without writing evidence")
    args = parser.parse_args()
    try:
        inventory = build_inventory()
    except (OSError, SyntaxError, ValueError) as exc:
        parser.error(str(exc))
    if not args.check:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(
        "PASS: source audit found one generic ledger writer, no production callers, "
        "and matching exact-location projection lineage in migrations 460 and 478"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
