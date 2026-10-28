#!/usr/bin/env python3
"""Inventory direct SQL execution calls across Kokonut service modules.

This report supports review of the shared PostgreSQL runtime role. It records
source locations, statement categories, regex-derived relation candidates, and
hashes for static SQL. It never stores SQL text or runtime parameter values and
must not be treated as an ACL or proof of complete database effects.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.worker_source_closure import build_inventory as build_worker_closure  # noqa: E402
from scripts.worker_sql_inventory import (  # noqa: E402
    EXECUTE_FUNCTIONS,
    EXECUTE_METHODS,
    _query_template,
    _SQLCallVisitor,
    _statement_kind,
    _write_target_relations,
)

_STATEMENT_GROUPS = {
    "read_candidate": {"SELECT"},
    "write_candidate": {"INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE"},
    "schema_change": {"CREATE", "ALTER", "DROP"},
    "transaction_or_session": {"SET", "SAVEPOINT", "ROLLBACK", "RELEASE"},
    "procedure_or_bulk": {"CALL", "COPY", "DO"},
}


def _statement_group(statement_kind: str) -> str:
    for group, kinds in _STATEMENT_GROUPS.items():
        if statement_kind in kinds:
            return group
    if statement_kind == "WITH":
        return "with_requires_manual_review"
    return "unknown_requires_manual_review"


def _target_binds_name(target: ast.expr, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_target_binds_name(element, name) for element in target.elts)
    return False


def _single_local_sql_assignment(
    function: ast.FunctionDef | ast.AsyncFunctionDef, name: str
) -> ast.AST | None:
    """Return one unambiguous local SQL assignment, or leave it unresolved.

    This deliberately does not follow helper calls, parameters, mutations,
    reassignment, loop bindings, or values selected from branches. The value
    itself can contain f-string substitutions; its literal SQL fragments are
    only candidates and dynamic relation identifiers are filtered later.
    """
    parameters = [
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    ]
    if function.args.vararg:
        parameters.append(function.args.vararg)
    if function.args.kwarg:
        parameters.append(function.args.kwarg)
    if any(parameter.arg == name for parameter in parameters):
        return None

    assignments: list[ast.AST] = []
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return None
        if isinstance(node, ast.Assign) and any(
            _target_binds_name(target, name) for target in node.targets
        ):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                return None
            assignments.append(node.value)
        elif isinstance(node, ast.AnnAssign) and _target_binds_name(node.target, name):
            if not isinstance(node.target, ast.Name) or node.value is None:
                return None
            assignments.append(node.value)
        elif isinstance(node, ast.NamedExpr) and _target_binds_name(node.target, name):
            if not isinstance(node.target, ast.Name):
                return None
            assignments.append(node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and _target_binds_name(node.target, name):
            return None
        elif isinstance(node, (ast.With, ast.AsyncWith)) and any(
            item.optional_vars and _target_binds_name(item.optional_vars, name)
            for item in node.items
        ):
            return None
        elif isinstance(node, ast.AugAssign) and _target_binds_name(node.target, name):
            return None
        elif isinstance(node, ast.ExceptHandler) and node.name == name:
            return None
        elif isinstance(node, ast.Delete) and any(
            _target_binds_name(target, name) for target in node.targets
        ):
            return None
        pending.extend(ast.iter_child_nodes(node))

    return assignments[0] if len(assignments) == 1 else None


class _ExecutionQueryContextVisitor(ast.NodeVisitor):
    """Keep local function and query-expression context for execution calls."""

    def __init__(self) -> None:
        self.functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.contexts: dict[tuple[int, int], tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, ast.AST]] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node)
        self.generic_visit(node)
        self.functions.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        method = None
        if isinstance(node.func, ast.Attribute) and node.func.attr in EXECUTE_METHODS:
            method = node.func.attr
        elif isinstance(node.func, ast.Name) and node.func.id in EXECUTE_FUNCTIONS:
            method = node.func.id
        if method:
            if method in EXECUTE_FUNCTIONS and len(node.args) >= 2:
                query_node = node.args[1]
            elif node.args:
                query_node = node.args[0]
            else:
                query_node = ast.Constant(value="")
            function = self.functions[-1] if self.functions else None
            self.contexts[(node.lineno, node.col_offset)] = (function, query_node)
        self.generic_visit(node)


def _candidate_relations_from_template(query: str) -> list[str]:
    """Do not report a truncated identifier next to an f-string placeholder."""
    candidates = []
    for match in re.finditer(
        r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE|REFERENCES|COPY)\s+"
        r'((?:"[^"\n]+"|[A-Za-z_][\w$]*)(?:\s*\.\s*(?:"[^"\n]+"|[A-Za-z_][\w$]*))?)',
        query,
        re.IGNORECASE,
    ):
        # `_query_template` marks each interpolation as `<dynamic>`. If it
        # touches the parsed identifier, the table name may be incomplete
        # (for example `public.{table}` or `{prefix}_event`). Keep the site
        # unresolved rather than inventing a relation candidate.
        suffix = query[match.end():]
        if re.match(r"\s*(?:\.\s*)?<dynamic>", suffix):
            continue
        raw_relation = match.group(1)
        relation = re.sub(r"\s*\.\s*", ".", raw_relation).replace('"', "")
        if '"' not in raw_relation and relation.upper() == "SET":
            # `ON CONFLICT ... DO UPDATE SET` must not be mistaken for the
            # relation following the UPDATE keyword.
            continue
        candidates.append(relation)
    return sorted(set(candidates))


def _scan_source(source: str, path: Path, operation_refs: list[str]) -> list[dict]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=source)
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise ValueError(f"Unable to parse runtime SQL source {source}") from exc
    visitor = _SQLCallVisitor(
        source, operation_refs, tree, include_write_targets=True
    )
    visitor.visit(tree)
    contexts = _ExecutionQueryContextVisitor()
    contexts.visit(tree)
    for site in visitor.sites:
        context = contexts.contexts.get((site["line"], site["column"]))
        if (
            context is not None
            and isinstance(context[1], ast.Name)
            and context[0] is not None
        ):
            assigned = _single_local_sql_assignment(context[0], context[1].id)
            if assigned is not None:
                query, query_kind = _query_template(assigned)
                # `_query_template` leaves a hole blank for arbitrary string
                # concatenation. Parsing that partial text could mistake a
                # schema prefix for a complete table name, so only literal
                # strings and f-strings with explicit placeholders are safe.
                if query_kind not in {"literal", "fstring"}:
                    site["statement_group"] = _statement_group(site["statement_kind"])
                    continue
                relations = _candidate_relations_from_template(query)
                statement_kind = _statement_kind(query)
                if relations or statement_kind != "UNKNOWN":
                    site["candidate_relations"] = sorted(
                        set(site["candidate_relations"]) | set(relations)
                    )
                    if site["statement_kind"] == "UNKNOWN" and statement_kind != "UNKNOWN":
                        site["statement_kind"] = statement_kind
                    write_targets = _write_target_relations(query, site["statement_kind"])
                    site["write_target_relations"] = [
                        relation for relation in write_targets if relation in relations
                    ]
                    site["local_query_resolution"] = "single_local_assignment_template"
        site["statement_group"] = _statement_group(site["statement_kind"])
    return visitor.sites


def _service_package(source: str) -> str:
    parts = source.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "services" else "<root>"


def build_inventory() -> dict:
    services_root = ROOT / "services"
    sources = sorted(services_root.rglob("*.py"))
    closure = build_worker_closure()
    operations_by_source: dict[str, set[str]] = defaultdict(set)
    for operation in closure["operations"]:
        operation_ref = f"{operation['kind']}:{operation['name']}"
        for source in operation["source_files"]:
            operations_by_source[source].add(operation_ref)

    sites = []
    for path in sources:
        source = path.relative_to(ROOT).as_posix()
        sites.extend(_scan_source(source, path, sorted(operations_by_source[source])))
    sites.sort(key=lambda item: (item["source"], item["line"], item["column"], item["method"]))

    statement_kinds = Counter(site["statement_kind"] for site in sites)
    expression_kinds = Counter(site["expression_kind"] for site in sites)
    package_sources: dict[str, set[str]] = defaultdict(set)
    for path in sources:
        source = path.relative_to(ROOT).as_posix()
        package_sources[_service_package(source)].add(source)
    package_sites: dict[str, list[dict]] = defaultdict(list)
    for site in sites:
        package_sites[_service_package(site["source"])].append(site)
    service_packages = {}
    for package in sorted(package_sources):
        package_rows = package_sites[package]
        service_packages[package] = {
            "source_files": len(package_sources[package]),
            "execution_sites": len(package_rows),
            "statement_groups": dict(sorted(Counter(
                row["statement_group"] for row in package_rows
            ).items())),
            "candidate_relation_names": len({
                relation for row in package_rows for relation in row["candidate_relations"]
            }),
            "sites_without_relation_candidates": sum(
                not row["candidate_relations"] for row in package_rows
            ),
            "non_literal_sites": sum(row["expression_kind"] != "literal" for row in package_rows),
            "sites_with_worker_operation_refs": sum(bool(row["operation_refs"]) for row in package_rows),
        }

    relations: dict[str, dict] = {}
    relation_sites: dict[str, list[dict]] = defaultdict(list)
    for site in sites:
        for relation in site["candidate_relations"]:
            relation_sites[relation].append(site)
    for relation, relation_rows in sorted(relation_sites.items()):
        relations[relation] = {
            "execution_site_count": len(relation_rows),
            "statement_kinds": sorted({row["statement_kind"] for row in relation_rows}),
            "statement_groups": sorted({row["statement_group"] for row in relation_rows}),
            "source_files": sorted({row["source"] for row in relation_rows}),
        }

    return {
        "version": 2,
        "generated_by": "scripts/runtime_sql_inventory.py",
        "scope": (
            "Direct Python SQL execution calls in services/**/*.py, including API, worker, "
            "and CLI modules. Relation names and simple leading DML targets are regex-derived "
            "candidates, not a parsed SQL AST. A query held in a local variable is resolved only "
            "from one unambiguous local assignment; dynamic table identifiers stay unresolved. "
            "The scan cannot prove query reachability, ORM/extension/external effects, complete "
            "database access, required columns, or authorization. It is not a grant allowlist."
        ),
        "summary": {
            "source_files": len(sources),
            "execution_sites": len(sites),
            "worker_operation_roots": len(closure["operations"]),
            "sites_with_worker_operation_refs": sum(bool(site["operation_refs"]) for site in sites),
            "sites_without_worker_operation_refs": sum(not site["operation_refs"] for site in sites),
            "statement_kinds": dict(sorted(statement_kinds.items())),
            "statement_groups": dict(sorted(Counter(site["statement_group"] for site in sites).items())),
            "expression_kinds": dict(sorted(expression_kinds.items())),
            "relation_candidates": len(relations),
            "write_target_relations": len({
                relation
                for site in sites
                for relation in site.get("write_target_relations", [])
            }),
            "sites_without_relation_candidates": sum(not site["candidate_relations"] for site in sites),
            "service_packages": len(service_packages),
        },
        "service_packages": service_packages,
        "relation_candidates": relations,
        "execution_sites": sites,
    }


def _serialize(value: dict) -> str:
    relation_candidates = value["relation_candidates"]
    execution_sites = value["execution_sites"]
    header = {key: item for key, item in value.items() if key not in {
        "relation_candidates",
        "execution_sites",
    }}
    serialized_header = json.dumps(header, indent=2)
    records = [
        "  \"relation_candidates\": {",
        ",\n".join(
            "    " + json.dumps(relation) + ": "
            + json.dumps(summary, separators=(",", ": "))
            for relation, summary in relation_candidates.items()
        ),
        "  },",
        "  \"execution_sites\": [",
        ",\n".join(
            "    " + json.dumps(site, separators=(",", ": "))
            for site in execution_sites
        ),
        "  ]",
    ]
    return serialized_header[:-1] + ",\n" + "\n".join(records) + "\n}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated inventory")
    group.add_argument("--check", type=Path, help="Fail if the saved inventory is stale")
    args = parser.parse_args(argv)
    expected = _serialize(build_inventory())

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        print(f"Wrote runtime SQL inventory: {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}")
        return 0

    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing runtime SQL inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Runtime SQL inventory is stale: {check}", file=sys.stderr)
        return 1
    print(f"Runtime SQL inventory is current: {check.relative_to(ROOT) if check.is_relative_to(ROOT) else check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
