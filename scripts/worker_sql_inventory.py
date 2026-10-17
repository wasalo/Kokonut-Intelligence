#!/usr/bin/env python3
"""Inventory direct SQL execution sites in allowlisted worker import closures.

The report stores source locations, candidate relation names, statement kinds,
and hashes for static SQL. It never copies SQL text or runtime values.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.worker_source_closure import build_inventory as build_source_closure  # noqa: E402

EXECUTE_METHODS = {"execute", "executemany", "executescript", "copy_expert", "copy_from", "copy_to"}
EXECUTE_FUNCTIONS = {"execute_values", "execute_batch"}
RELATION_PATTERN = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE|REFERENCES|COPY)\s+"
    r'((?:"[^"\n]+"|[A-Za-z_][\w$]*)(?:\s*\.\s*(?:"[^"\n]+"|[A-Za-z_][\w$]*))?)',
    re.IGNORECASE,
)
STATEMENT_PATTERN = re.compile(
    r"^\s*(?:--[^\n]*\n\s*)*(SELECT|INSERT|UPDATE|DELETE|WITH|MERGE|CREATE|ALTER|DROP|TRUNCATE|CALL|COPY|SET|DO|SAVEPOINT|ROLLBACK|RELEASE)\b",
    re.IGNORECASE,
)


def _query_template(node: ast.AST) -> tuple[str, str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, "literal"
    if isinstance(node, ast.Call) and node.args:
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"text", "SQL"}:
            # SQLAlchemy text() and psycopg composable SQL() wrap a query
            # template; inspect only the first string argument, never values.
            return _query_template(node.args[0])
        if isinstance(node.func, ast.Name) and node.func.id in {"text", "SQL"}:
            return _query_template(node.args[0])
    if isinstance(node, ast.JoinedStr):
        pieces = []
        has_dynamic = False
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append(value.value)
            else:
                pieces.append(" <dynamic> ")
                has_dynamic = True
        return "".join(pieces), "fstring" if has_dynamic else "literal"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, left_kind = _query_template(node.left)
        right, right_kind = _query_template(node.right)
        kind = "literal" if left_kind == right_kind == "literal" else "composed"
        return left + right, kind
    return "", "composed_or_variable"


def _normalized_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _candidate_relations(query: str) -> list[str]:
    found = set()
    for match in RELATION_PATTERN.finditer(query):
        relation = re.sub(r"\s*\.\s*", ".", match.group(1))
        relation = relation.replace('"', "")
        found.add(relation)
    return sorted(found)


def _statement_kind(query: str) -> str:
    match = STATEMENT_PATTERN.search(query)
    return match.group(1).upper() if match else "UNKNOWN"


def _local_statement_kind(function: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> str:
    """Infer a local SQL variable's leading statement when all assignments agree."""
    parameters = [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
    if function.args.vararg:
        parameters.append(function.args.vararg)
    if function.args.kwarg:
        parameters.append(function.args.kwarg)
    if any(parameter.arg == name for parameter in parameters):
        return "UNKNOWN"

    assigned_templates = []
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        elif isinstance(node, ast.NamedExpr):
            targets = [node.target]
            value = node.value
        elif isinstance(node, (ast.For, ast.AsyncFor)) and _target_binds_name(node.target, name):
            assigned_templates.append("UNKNOWN")
        elif isinstance(node, (ast.With, ast.AsyncWith)) and any(
            item.optional_vars and _target_binds_name(item.optional_vars, name) for item in node.items
        ):
            assigned_templates.append("UNKNOWN")
        elif isinstance(node, ast.AugAssign) and _target_binds_name(node.target, name):
            if not isinstance(node.op, ast.Add):
                assigned_templates.append("UNKNOWN")
        elif isinstance(node, ast.ExceptHandler) and node.name == name:
            assigned_templates.append("UNKNOWN")
        if value is not None and any(isinstance(target, ast.Name) and target.id == name for target in targets):
            query, _ = _query_template(value)
            assigned_templates.append(_statement_kind(query))
        pending.extend(ast.iter_child_nodes(node))

    kinds = set(assigned_templates)
    return next(iter(kinds)) if assigned_templates and len(kinds) == 1 and "UNKNOWN" not in kinds else "UNKNOWN"


def _target_binds_name(target: ast.expr, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_target_binds_name(element, name) for element in target.elts)
    return False


class _SQLCallVisitor(ast.NodeVisitor):
    def __init__(self, source: str, operations: list[str]):
        self.source = source
        self.operations = operations
        self.scope: list[str] = []
        self.functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.sites: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.functions.append(node)
        self.generic_visit(node)
        self.functions.pop()
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        method = None
        if isinstance(node.func, ast.Attribute) and node.func.attr in EXECUTE_METHODS:
            method = node.func.attr
        elif isinstance(node.func, ast.Name) and node.func.id in EXECUTE_FUNCTIONS:
            method = node.func.id
        if method:
            self.sites.append(self._site(node, method))
        self.generic_visit(node)

    def _site(self, node: ast.Call, method: str) -> dict:
        if method in EXECUTE_FUNCTIONS and len(node.args) >= 2:
            query_node = node.args[1]
        elif node.args:
            query_node = node.args[0]
        else:
            query_node = ast.Constant(value="")
        query, expression_kind = _query_template(query_node)
        normalized = _normalized_query(query)
        statement_kind = _statement_kind(query)
        if statement_kind == "UNKNOWN" and isinstance(query_node, ast.Name) and self.functions:
            statement_kind = _local_statement_kind(self.functions[-1], query_node.id)
        fingerprint = None
        if expression_kind == "literal" and normalized:
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return {
            "id": f"{self.source}:{node.lineno}:{node.col_offset}",
            "source": self.source,
            "line": node.lineno,
            "column": node.col_offset,
            "scope": ".".join(self.scope) if self.scope else "module",
            "method": method,
            "expression_kind": expression_kind,
            "statement_kind": statement_kind,
            "candidate_relations": _candidate_relations(query),
            "static_sql_sha256": fingerprint,
            "operation_refs": self.operations,
        }


def build_inventory() -> dict:
    closure = build_source_closure()
    operations_by_file: dict[str, set[str]] = defaultdict(set)
    for operation in closure["operations"]:
        reference = f"{operation['kind']}:{operation['name']}"
        for source in operation["source_files"]:
            operations_by_file[source].add(reference)

    sites = []
    for source, operation_refs in sorted(operations_by_file.items()):
        path = ROOT / source
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=source)
        except (OSError, SyntaxError) as exc:
            raise ValueError(f"Unable to parse worker SQL source {source}") from exc
        visitor = _SQLCallVisitor(source, sorted(operation_refs))
        visitor.visit(tree)
        sites.extend(visitor.sites)

    sites.sort(key=lambda item: (item["source"], item["line"], item["column"], item["method"]))
    dynamic = [site for site in sites if site["expression_kind"] != "literal"]
    return {
        "version": 1,
        "generated_by": "scripts/worker_sql_inventory.py",
        "scope": (
            "Direct Python SQL execution calls found in the static worker source-import closure. "
            "Relation names are regex-derived candidates, not a parsed SQL AST. The inventory "
            "does not prove function reachability, complete database effects, or authorization."
        ),
        "summary": {
            "operation_roots": len(closure["operations"]),
            "source_files": len(operations_by_file),
            "execution_sites": len(sites),
            "static_literal_sites": len(sites) - len(dynamic),
            "composed_or_variable_sites": len(dynamic),
        },
        "execution_sites": sites,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


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
        return 0

    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing worker SQL inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Worker SQL inventory is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
