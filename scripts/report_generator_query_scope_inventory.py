#!/usr/bin/env python3
"""Inventory visible query scope in registered report generator source."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

from report_generator_inventory import ROOT
from report_generator_inventory import build_inventory as build_inventory_source

_QUERY_METHODS = {"execute", "query"}
_LOCATION_PREDICATE = re.compile(
    r"\b(?:[a-z_][a-z0-9_]*\.)?location_id\s*(?:=|<>|!=|\bin\b|\bis\b|\bany\b)",
    re.IGNORECASE,
)
_LOCATION_ROW_LOOKUP = re.compile(
    r"\bfrom\s+(?:[a-z_][a-z0-9_]*\.)?location\b[\s\S]*?\bwhere\s+(?:[a-z_][a-z0-9_]*\.)?id\s*=",
    re.IGNORECASE,
)
_INDIRECT_LOCATION_SCOPE = (
    re.compile(
        r"\bsubject_type\s*=\s*['\"]location['\"][\s\S]*?\bsubject_id\s*=\s*(?:%s|:[a-z_][a-z0-9_]*|\$\d+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsubject_id\s*=\s*(?:%s|:[a-z_][a-z0-9_]*|\$\d+)[\s\S]*?\bsubject_type\s*=\s*['\"]location['\"]",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bscope_type\s*=\s*['\"]location['\"][\s\S]*?\bscope_id\s*=\s*(?:%s|:[a-z_][a-z0-9_]*|\$\d+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bidentifier_type\s*=\s*['\"]location_id['\"][\s\S]*?\bidentifier_value\s*=\s*(?:%s|:[a-z_][a-z0-9_]*|\$\d+)",
        re.IGNORECASE,
    ),
)
_NULL_LOCATION = re.compile(
    r"\b(?:[a-z_][a-z0-9_]*\.)?location_id\s+is\s+null\b", re.IGNORECASE
)
_RELATION = re.compile(
    r"\b(?:from|join)\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)",
    re.IGNORECASE,
)


def _string_sequence(
    node: ast.AST, assignments: dict[str, list[tuple[int, ast.AST]]], before: int
) -> list[str] | None:
    if isinstance(node, (ast.List, ast.Tuple)):
        parts = [_string_value(value, assignments, before) for value in node.elts]
        return [part for part in parts if part is not None] if all(part is not None for part in parts) else None
    if isinstance(node, ast.Name):
        candidates = [value for line, value in assignments.get(node.id, []) if line < before]
        return _string_sequence(candidates[-1], assignments, before) if candidates else None
    return None


def _string_value(node: ast.AST, assignments: dict[str, list[tuple[int, ast.AST]]], before: int) -> str | None:
    """Resolve common literal SQL construction without evaluating Python."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        candidates = [value for line, value in assignments.get(node.id, []) if line < before]
        return _string_value(candidates[-1], assignments, before) if candidates else None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                resolved = _string_value(value.value, assignments, before)
                if resolved is None:
                    return None
                parts.append(resolved)
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _string_value(node.left, assignments, before)
        right = _string_value(node.right, assignments, before)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.Call):
        # SQLAlchemy's text(sql) wrapper is transparent for source inventory.
        if isinstance(node.func, ast.Attribute) and node.func.attr == "text" and node.args:
            return _string_value(node.args[0], assignments, before)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
            and isinstance(node.func.value, ast.Constant)
            and isinstance(node.func.value.value, str)
            and len(node.args) == 1
        ):
            parts = _string_sequence(node.args[0], assignments, before)
            if parts is not None:
                return node.func.value.value.join(parts)
    return None


def _expression_mentions_location_id(node: ast.AST | None, assignments: dict[str, list[tuple[int, ast.AST]]], before: int) -> bool:
    if node is None:
        return False
    pending = [item.id for item in ast.walk(node) if isinstance(item, ast.Name)]
    resolved_names: set[str] = set()
    while pending:
        name = pending.pop()
        if name in resolved_names:
            continue
        resolved_names.add(name)
        candidates = [value for line, value in assignments.get(name, []) if line < before]
        if candidates:
            pending.extend(
                item.id for item in ast.walk(candidates[-1]) if isinstance(item, ast.Name)
            )
    return "location_id" in resolved_names


def _sql_bind_counts(sql: str) -> tuple[int, bool]:
    """Count positional %s binds outside SQL literals/comments and detect named binds."""
    code: list[str] = []
    index = 0
    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""
        if char == "'" or char == '"':
            quote = char
            index += 1
            while index < len(sql):
                if sql[index] == "\\":
                    index += 2
                    continue
                if sql[index] == quote:
                    if index + 1 < len(sql) and sql[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            code.append(" ")
            continue
        if char == "-" and following == "-":
            newline = sql.find("\n", index + 2)
            index = len(sql) if newline < 0 else newline + 1
            code.append(" ")
            continue
        if char == "/" and following == "*":
            index += 2
            depth = 1
            while index < len(sql) and depth:
                if sql.startswith("/*", index):
                    depth += 1
                    index += 2
                elif sql.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            code.append(" ")
            continue
        if char == "$":
            delimiter = re.match(r"\$[a-zA-Z_][a-zA-Z0-9_]*\$|\$\$", sql[index:])
            if delimiter:
                token = delimiter.group(0)
                end = sql.find(token, index + len(token))
                index = len(sql) if end < 0 else end + len(token)
                code.append(" ")
                continue
        code.append(char)
        index += 1

    executable_sql = "".join(code)
    positional_count = 0
    index = 0
    while index < len(executable_sql):
        if executable_sql.startswith("%%", index):
            index += 2
        elif executable_sql.startswith("%s", index):
            positional_count += 1
            index += 2
        else:
            index += 1
    named_bind = bool(
        re.search(r"%\([a-zA-Z_][a-zA-Z0-9_]*\)s", executable_sql)
        or re.search(r"(?<!:):[a-zA-Z_][a-zA-Z0-9_]*", executable_sql)
    )
    return positional_count, named_bind


def _known_parameter_count(
    node: ast.AST | None,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    before: int,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int | None:
    """Resolve only simple positional parameter containers; skip dynamic mappings/lists."""
    if node is None or isinstance(node, ast.Constant) and node.value is None:
        return 0
    if isinstance(node, (ast.Tuple, ast.List)):
        return None if any(isinstance(item, ast.Starred) for item in node.elts) else len(node.elts)
    if isinstance(node, ast.Dict):
        return None
    if isinstance(node, ast.Name):
        if any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in {"append", "extend", "update"}
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == node.id
            and call.lineno < before
            for call in ast.walk(function)
        ) or any(
            isinstance(statement, ast.AugAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == node.id
            and statement.lineno < before
            for statement in ast.walk(function)
        ):
            return None
        candidates = [value for line, value in assignments.get(node.id, []) if line < before]
        return _known_parameter_count(candidates[-1], assignments, before, function) if candidates else None
    return 1


def _positional_bind_arity(
    sql: str | None,
    call: ast.Call,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict | None:
    if sql is None:
        return None
    placeholder_count, named_binds = _sql_bind_counts(sql)
    if named_binds:
        return None
    positional_index = 2 if isinstance(call.func, ast.Name) and call.func.id == "query" else 1
    parameter_node = call.args[positional_index] if len(call.args) > positional_index else next(
        (keyword.value for keyword in call.keywords if keyword.arg in {"params", "parameters"}),
        None,
    )
    supplied_count = _known_parameter_count(parameter_node, assignments, call.lineno, function)
    if supplied_count is None:
        return None
    return {
        "placeholder_count": placeholder_count,
        "supplied_count": supplied_count,
        "mismatch": placeholder_count != supplied_count,
    }


def _assigned_values(function: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, list[tuple[int, ast.AST]]]:
    assignments: dict[str, list[tuple[int, ast.AST]]] = {}
    for node in sorted(ast.walk(function), key=lambda item: getattr(item, "lineno", 0)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append((node.lineno, node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            assignments.setdefault(node.target.id, []).append((node.lineno, node.value))
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            previous = [value for line, value in assignments.get(node.target.id, []) if line < node.lineno]
            if isinstance(node.op, ast.Add) and previous:
                left = _string_value(previous[-1], assignments, node.lineno)
                right = _string_value(node.value, assignments, node.lineno)
                value: ast.AST = ast.Constant(value=left + right) if left is not None and right is not None else ast.Constant(value=None)
            else:
                value = ast.Constant(value=None)
            assignments.setdefault(node.target.id, []).append((node.lineno, value))
    for values in assignments.values():
        values.sort(key=lambda item: item[0])
    return assignments


def _conditional_assignment_variants(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    before: int,
) -> list[tuple[tuple[int, int], int, ast.AST]]:
    """Resolve the last value assigned to a name in location-conditional branches."""
    variants: list[tuple[tuple[int, int], int, ast.AST]] = []
    for node in ast.walk(function):
        if (
            not isinstance(node, ast.If)
            or node.lineno >= before
            or not _expression_mentions_location_id(node.test, assignments, node.lineno)
        ):
            continue
        branch_values: list[list[tuple[int, ast.AST]]] = []
        branch_lines: set[int] = set()
        for branch_index, branch in enumerate((node.body, node.orelse)):
            lines = set()
            for child in ast.walk(ast.Module(body=branch, type_ignores=[])):
                if isinstance(child, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == name for target in child.targets
                ):
                    lines.add(child.lineno)
                elif isinstance(child, (ast.AnnAssign, ast.AugAssign)) and isinstance(
                    child.target, ast.Name
                ) and child.target.id == name:
                    lines.add(child.lineno)
            branch_lines.update(lines)
            branch_values.append(
                [(line, value) for line, value in assignments.get(name, []) if line in lines]
            )
        if not any(branch_values):
            continue
        latest_assignment = max(
            (line for line, _value in assignments.get(name, []) if line < before),
            default=-1,
        )
        if latest_assignment not in branch_lines:
            continue
        prior = [(line, value) for line, value in assignments.get(name, []) if line < node.lineno]
        for branch_index, values in enumerate(branch_values):
            if values:
                line, value = values[-1]
                variants.append(((node.lineno, branch_index), line, value))
            elif prior:
                line, value = prior[-1]
                variants.append(((node.lineno, branch_index), line, value))
    return variants


def _location_branch_index(
    function: ast.FunctionDef | ast.AsyncFunctionDef, conditional_line: int
) -> int | None:
    """Return the branch index that requires a supplied location, if obvious."""
    conditional = next(
        (
            node
            for node in ast.walk(function)
            if isinstance(node, ast.If) and node.lineno == conditional_line
        ),
        None,
    )
    if conditional is None:
        return None

    test = conditional.test
    negated = False
    while isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        negated = not negated
        test = test.operand
    branch_for_present_location: int | None = None
    if isinstance(test, ast.Name) and test.id == "location_id":
        branch_for_present_location = 0
    elif (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "location_id"
        and len(test.ops) == 1
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    ):
        if isinstance(test.ops[0], (ast.IsNot, ast.NotEq)):
            branch_for_present_location = 0
        elif isinstance(test.ops[0], (ast.Is, ast.Eq)):
            branch_for_present_location = 1
    if branch_for_present_location is None:
        return None
    return 1 - branch_for_present_location if negated else branch_for_present_location


def _query_argument(call: ast.Call) -> ast.AST | None:
    if isinstance(call.func, ast.Name) and call.func.id == "query":
        return call.args[1] if len(call.args) > 1 else None
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Call) and isinstance(first.func, ast.Attribute) and first.func.attr == "text":
        return first.args[0] if first.args else None
    return first


def _query_calls(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    assignments = _assigned_values(function)
    queries = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in _QUERY_METHODS:
            method = node.func.attr
            parameter_nodes = [*node.args[1:], *(keyword.value for keyword in node.keywords)]
        elif isinstance(node.func, ast.Name) and node.func.id == "query":
            method = "query"
            parameter_nodes = [*node.args[2:], *(keyword.value for keyword in node.keywords)]
        else:
            continue
        sql_node = _query_argument(node)
        sql = _string_value(sql_node, assignments, node.lineno) if sql_node else None
        sql_variants = [sql]
        conditional_sql_variants = []
        sql_variant_paths: list[tuple[tuple[int, int] | None, str | None]] = [(None, sql)]
        if isinstance(sql_node, ast.Name):
            conditional_sql_variants = _conditional_assignment_variants(
                function, sql_node.id, assignments, node.lineno
            )
            if conditional_sql_variants:
                sql_variants = [
                    _string_value(value, assignments, line)
                    for _path, line, value in conditional_sql_variants
                ]
                sql = next((value for value in reversed(sql_variants) if value is not None), sql)
                sql_variant_paths = [
                    (path, _string_value(value, assignments, line))
                    for path, line, value in conditional_sql_variants
                ]
        positional_arity = (
            None
            if conditional_sql_variants
            else _positional_bind_arity(sql, node, assignments, function)
        )
        resolved_sql_variants = [value for value in sql_variants if value is not None]
        parameter_variable_names = {
            name.id for param in parameter_nodes for name in ast.walk(param) if isinstance(name, ast.Name)
        }
        parameter_paths: set[tuple[int, int]] = set()
        params_include_location = False
        for param in parameter_nodes:
            conditional_names = {
                name.id
                for name in ast.walk(param)
                if isinstance(name, ast.Name)
                and _conditional_assignment_variants(
                    function, name.id, assignments, node.lineno
                )
            }
            if not conditional_names and _expression_mentions_location_id(
                param, assignments, node.lineno
            ):
                params_include_location = True
        for name in parameter_variable_names:
            for path, line, value in _conditional_assignment_variants(
                function, name, assignments, node.lineno
            ):
                if _expression_mentions_location_id(value, assignments, line):
                    parameter_paths.add(path)
        if parameter_paths:
            # A static SQL statement is shared by every parameter branch. When
            # SQL is conditional, the path set below keeps its bind evidence
            # paired with the matching SQL branch.
            params_include_location = True
        if not params_include_location:
            for mutation in ast.walk(function):
                if (
                    isinstance(mutation, ast.Call)
                    and isinstance(mutation.func, ast.Attribute)
                    and mutation.func.attr in {"append", "extend"}
                    and isinstance(mutation.func.value, ast.Name)
                    and mutation.func.value.id in parameter_variable_names
                    and mutation.lineno < node.lineno
                    and any(
                        _expression_mentions_location_id(arg, assignments, mutation.lineno)
                        for arg in mutation.args
                    )
                ):
                    params_include_location = True
                    break
        relations = sorted({
            match.lower()
            for query_sql in resolved_sql_variants
            for match in _RELATION.findall(query_sql)
        })
        location_id_reference = any(
            re.search(r"\blocation_id\b", query_sql, re.IGNORECASE)
            for query_sql in resolved_sql_variants
        )
        location_predicate = any(
            _LOCATION_PREDICATE.search(query_sql) for query_sql in resolved_sql_variants
        )
        location_row_lookup = any(
            _LOCATION_ROW_LOOKUP.search(query_sql) for query_sql in resolved_sql_variants
        )
        indirect_location_scope = any(
            pattern.search(query_sql)
            for pattern in _INDIRECT_LOCATION_SCOPE
            for query_sql in resolved_sql_variants
        )
        location_bound = params_include_location
        scoped_sql_paths = {
            path
            for path, query_sql in sql_variant_paths
            if query_sql
            and (
                _LOCATION_PREDICATE.search(query_sql)
                or _LOCATION_ROW_LOOKUP.search(query_sql)
                or any(pattern.search(query_sql) for pattern in _INDIRECT_LOCATION_SCOPE)
            )
            and (
                path is None
                or path[1] == _location_branch_index(function, path[0])
            )
        }
        correlated_location_binding = location_bound and bool(scoped_sql_paths) and (
            not conditional_sql_variants
            or not parameter_paths
            or any(path in parameter_paths for path in scoped_sql_paths)
        )
        queries.append(
            {
                "line": node.lineno,
                "method": method,
                "sql_source": (
                    "static_or_resolved"
                    if resolved_sql_variants and len(resolved_sql_variants) == len(sql_variants)
                    else "dynamic_or_unresolved"
                ),
                "relations": relations,
                "location_id_reference": location_id_reference,
                "location_predicate_visible": location_predicate,
                "global_null_rows_allowed": any(
                    _NULL_LOCATION.search(query_sql) for query_sql in resolved_sql_variants
                ),
                "location_id_in_bound_expression": params_include_location,
                "location_row_lookup_by_id": location_row_lookup,
                "indirect_location_scope_visible": indirect_location_scope,
                "location_scope_conditionally_added": bool(conditional_sql_variants),
                "bound_location_scope_signal": location_bound
                and (location_predicate or location_row_lookup or indirect_location_scope)
                and correlated_location_binding,
                "positional_bind_arity": positional_arity,
            }
        )
    return sorted(queries, key=lambda item: (item["line"], item["method"]))


def _helper_calls(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    assignments = _assigned_values(function)
    calls: dict[tuple[str, int], bool] = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in _QUERY_METHODS:
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name.startswith(("get_", "fetch_", "load_", "build_", "query_", "compute_", "assemble_", "collect_", "generate_")):
                args = [*node.args, *(keyword.value for keyword in node.keywords)]
                calls[(name, node.lineno)] = any(
                    _expression_mentions_location_id(arg, assignments, node.lineno) for arg in args
                )
        elif isinstance(node.func, ast.Attribute) and node.func.attr.startswith(("get_", "fetch_", "load_", "build_", "query_")):
            args = [*node.args, *(keyword.value for keyword in node.keywords)]
            calls[(ast.unparse(node.func), node.lineno)] = any(
                _expression_mentions_location_id(arg, assignments, node.lineno) for arg in args
            )
    return [
        {"callable": name, "line": line, "location_id_name_visible_in_arguments": forwarded}
        for (name, line), forwarded in sorted(calls.items())
    ]


def _analyze_function(function: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    queries = _query_calls(function)
    scope_signal_count = sum(query["bound_location_scope_signal"] for query in queries)
    unresolved_count = sum(query["sql_source"] != "static_or_resolved" for query in queries)
    conditional_count = sum(query["location_scope_conditionally_added"] for query in queries)
    if not queries:
        classification = "helper_or_computed_without_direct_query"
    elif unresolved_count and scope_signal_count < len(queries):
        classification = "partial_or_unresolved_direct_query_scope"
    elif scope_signal_count == len(queries) and conditional_count and not unresolved_count:
        classification = "conditional_direct_query_scope"
    elif scope_signal_count == len(queries) and unresolved_count == 0:
        classification = "all_direct_queries_show_bound_location_scope"
    elif scope_signal_count:
        classification = "mixed_direct_query_scope"
    elif unresolved_count:
        classification = "direct_query_scope_unresolved"
    else:
        classification = "no_bound_location_scope_visible"
    return {
        "classification": classification,
        "direct_query_count": len(queries),
        "static_positional_arity_site_count": sum(
            query["positional_bind_arity"] is not None for query in queries
        ),
        "positional_arity_mismatch_count": sum(
            query["positional_bind_arity"] is not None
            and query["positional_bind_arity"]["mismatch"]
            for query in queries
        ),
        "queries_with_bound_location_scope_signal": scope_signal_count,
        "conditional_scope_query_count": conditional_count,
        "unresolved_query_count": unresolved_count,
        "helper_calls": _helper_calls(function),
        "queries": queries,
    }


def analyze_function_source(source: str, function_name: str) -> dict:
    """Expose the conservative classifier for focused synthetic unit tests."""
    tree = ast.parse(source)
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
    )
    return _analyze_function(function)


def build_inventory() -> dict:
    source_inventory = build_inventory_source()
    entries = []
    classification_counts: dict[str, int] = {}
    total_queries = 0
    static_positional_arity_sites = 0
    positional_arity_mismatches = 0
    scope_signal_queries = 0
    conditional_scope_queries = 0
    unresolved_queries = 0
    for report in source_inventory["reports"]:
        source_path = ROOT / report["source_file"]
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == report["callable"]
        )
        analysis = _analyze_function(function)
        classification_counts[analysis["classification"]] = (
            classification_counts.get(analysis["classification"], 0) + 1
        )
        total_queries += analysis["direct_query_count"]
        static_positional_arity_sites += analysis["static_positional_arity_site_count"]
        positional_arity_mismatches += analysis["positional_arity_mismatch_count"]
        scope_signal_queries += analysis["queries_with_bound_location_scope_signal"]
        conditional_scope_queries += analysis["conditional_scope_query_count"]
        unresolved_queries += analysis["unresolved_query_count"]
        entries.append(
            {
                "report_type": report["report_type"],
                "callable": report["callable"],
                "source_file": report["source_file"],
                "source_line": report["source_line"],
                **analysis,
            }
        )

    return {
        "version": 1,
        "generated_by": "scripts/report_generator_query_scope_inventory.py",
        "scope": (
            "Conservative AST inventory of direct execute/query calls in registered report functions. "
        "Location-dependent SQL assignment branches retain all statically resolved variants. "
            "For unbranched static SQL and statically known positional parameter containers, it also compares %s placeholder and supplied-value counts; named and dynamic bindings are left unresolved. "
            "A visible location predicate or bound location_id expression is only a source signal; it does not "
            "prove correct authorization, tenant isolation, view lineage, or semantic filtering. Helper behavior, "
            "database policies, dynamic SQL, and runtime inputs may change effective scope. No report is run, "
            "no query is executed, and no database, provider, saved query, or secret is accessed."
        ),
        "summary": {
            "registered_report_types": len(entries),
            "direct_query_sites": total_queries,
            "static_positional_arity_sites": static_positional_arity_sites,
            "positional_arity_mismatch_sites": positional_arity_mismatches,
            "query_sites_with_bound_location_scope_signal": scope_signal_queries,
            "conditional_scope_query_sites": conditional_scope_queries,
            "unresolved_query_sites": unresolved_queries,
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "reports": sorted(entries, key=lambda entry: entry["report_type"]),
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated query-scope inventory")
    group.add_argument("--check", type=Path, help="Fail if a saved inventory is stale")
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
        print(f"Missing report query-scope inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Report query-scope inventory is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
