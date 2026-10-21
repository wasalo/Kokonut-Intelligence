#!/usr/bin/env python3
"""Inventory visible query scope in registered report generator source."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from itertools import product
from pathlib import Path

from report_generator_inventory import ROOT
from report_generator_inventory import build_inventory as build_inventory_source

_QUERY_METHODS = {"execute", "query"}
_LOCATION_PREDICATE = re.compile(
    r"\b(?:[a-z_][a-z0-9_]*\.)?location_id\s*(?:=|<>|!=|\bin\b|\bis\b|\bany\b)",
    re.IGNORECASE,
)
_LOCATION_JOIN_ALIAS = re.compile(
    r"\b(?:from|join)\s+(?:public\.)?location\s+(?:as\s+)?"
    r"([a-z_][a-z0-9_]*)\s+on\b",
    re.IGNORECASE,
)
_JOINED_LOCATION_ID_PREDICATE = re.compile(
    r"\b([a-z_][a-z0-9_]*)\.id\s*=\s*%s\b",
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


def _sql_executable_text(sql: str) -> str:
    """Remove SQL strings, quoted identifiers, comments, and dollar bodies."""
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

    return "".join(code)


def _sql_named_bind_names(sql: str) -> set[str]:
    """Return named placeholder keys outside SQL literals and comments."""
    executable_sql = _sql_executable_text(sql).replace("%%(", "   (")
    names: set[str] = set()
    for psycopg_name, sqlalchemy_name in re.findall(
        r"%\(([a-zA-Z_][a-zA-Z0-9_]*)\)s|(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)",
        executable_sql,
    ):
        names.add(psycopg_name or sqlalchemy_name)
    return names


def _sql_bind_counts(sql: str) -> tuple[int, bool]:
    """Count positional %s binds outside SQL literals/comments and detect named binds."""
    executable_sql = _sql_executable_text(sql)
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
    named_bind = bool(_sql_named_bind_names(sql))
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


def _parameter_list_mutation_branch(
    mutation: ast.Call,
    parents: dict[ast.AST, ast.AST],
    conditional_path: tuple[int, int],
) -> str | None:
    """Classify a simple list mutation as unconditional or on one known branch."""
    current: ast.AST = mutation
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.If):
            if parent.lineno != conditional_path[0]:
                return None
            branch_root = current
            while parents.get(branch_root) is not parent:
                branch_root = parents[branch_root]
            if branch_root in parent.body:
                return "selected" if conditional_path[1] == 0 else "other"
            if branch_root in parent.orelse:
                return "selected" if conditional_path[1] == 1 else "other"
            return None
        if isinstance(parent, (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match)):
            return None
        current = parent
    return "unconditional"


def _known_parameter_count_for_branch(
    node: ast.AST | None,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    before: int,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    branch_path: tuple[int, int],
) -> int | None:
    """Resolve a positional list only when its mutations align with a SQL branch."""
    if not isinstance(node, ast.Name):
        return _known_parameter_count(node, assignments, before, function)

    name = node.id
    variants = _conditional_assignment_variants(function, name, assignments, before)
    matching_variants = [
        (line, value) for path, line, value in variants if path == branch_path
    ]
    if variants:
        if len(matching_variants) != 1:
            return None
        assignment_line, value = matching_variants[0]
        # A branch-selected literal is safe only when no later mutation changes
        # the selected parameter list before execution.
        if any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == name
            and assignment_line < call.lineno < before
            for call in ast.walk(function)
        ):
            return None
        return _known_parameter_count(value, assignments, assignment_line, function)

    candidates = [
        (line, value) for line, value in assignments.get(name, []) if line < before
    ]
    if not candidates:
        return None
    assignment_line, initial_value = candidates[-1]
    if not isinstance(initial_value, (ast.List, ast.Tuple)) or any(
        isinstance(item, ast.Starred) for item in initial_value.elts
    ):
        return None
    count = len(initial_value.elts)

    parents = {
        child: parent
        for parent in ast.walk(function)
        for child in ast.iter_child_nodes(parent)
    }
    for node_in_function in ast.walk(function):
        if isinstance(node_in_function, ast.AugAssign) and isinstance(
            node_in_function.target, ast.Name
        ) and node_in_function.target.id == name and assignment_line < node_in_function.lineno < before:
            return None
        if not isinstance(node_in_function, ast.Call) or not (
            isinstance(node_in_function.func, ast.Attribute)
            and isinstance(node_in_function.func.value, ast.Name)
            and node_in_function.func.value.id == name
            and assignment_line < node_in_function.lineno < before
        ):
            continue

        method = node_in_function.func.attr
        if method not in {"append", "extend"}:
            return None
        mutation_branch = _parameter_list_mutation_branch(
            node_in_function, parents, branch_path
        )
        if mutation_branch is None:
            return None
        if mutation_branch == "other":
            continue
        if method == "append":
            if len(node_in_function.args) != 1 or node_in_function.keywords:
                return None
            count += 1
        else:
            if len(node_in_function.args) != 1 or node_in_function.keywords:
                return None
            extension_count = _known_parameter_count(
                node_in_function.args[0], assignments, node_in_function.lineno, function
            )
            if extension_count is None:
                return None
            count += extension_count
    return count


def _positional_bind_arity(
    sql: str | None,
    call: ast.Call,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    conditional_sql_variants: list[tuple[tuple[int, int], int, ast.AST]] | None = None,
) -> dict | None:
    positional_index = 2 if isinstance(call.func, ast.Name) and call.func.id == "query" else 1
    parameter_node = call.args[positional_index] if len(call.args) > positional_index else next(
        (keyword.value for keyword in call.keywords if keyword.arg in {"params", "parameters"}),
        None,
    )

    if conditional_sql_variants:
        variants = []
        for branch_path, sql_line, sql_node in conditional_sql_variants:
            branch_sql = _string_value(sql_node, assignments, sql_line)
            if branch_sql is None:
                return None
            placeholder_count, named_binds = _sql_bind_counts(branch_sql)
            if named_binds:
                return None
            supplied_count = _known_parameter_count_for_branch(
                parameter_node, assignments, call.lineno, function, branch_path
            )
            if supplied_count is None:
                return None
            variants.append(
                {
                    "conditional_line": branch_path[0],
                    "branch": branch_path[1],
                    "placeholder_count": placeholder_count,
                    "supplied_count": supplied_count,
                    "mismatch": placeholder_count != supplied_count,
                }
            )
        return {"mismatch": any(item["mismatch"] for item in variants), "variants": variants}

    if sql is None:
        return None
    placeholder_count, named_binds = _sql_bind_counts(sql)
    if named_binds:
        return None
    supplied_count = _known_parameter_count(parameter_node, assignments, call.lineno, function)
    if supplied_count is None:
        return None
    return {
        "placeholder_count": placeholder_count,
        "supplied_count": supplied_count,
        "mismatch": placeholder_count != supplied_count,
    }


def _simple_branch_path(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> tuple[int, int] | tuple[()] | None:
    """Return one enclosing if branch, (), or None for unsupported control flow."""
    current = node
    branch_path: tuple[int, int] | None = None
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.If):
            if branch_path is not None:
                return None
            branch_root = current
            while parents.get(branch_root) is not parent:
                branch_root = parents[branch_root]
            if branch_root in parent.body:
                branch_path = (parent.lineno, 0)
            elif branch_root in parent.orelse:
                branch_path = (parent.lineno, 1)
            else:
                return None
        elif isinstance(parent, (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match)):
            return None
        current = parent
    return branch_path if branch_path is not None else ()


def _expression_assignment_closure(
    node: ast.AST,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    before: int,
) -> list[ast.AST]:
    """Follow simple local names used to construct a SQL expression."""
    expressions: list[ast.AST] = []
    pending = [node]
    visited_names: set[str] = set()
    while pending:
        expression = pending.pop()
        expressions.append(expression)
        for child in ast.walk(expression):
            if not isinstance(child, ast.Name) or child.id in visited_names:
                continue
            visited_names.add(child.id)
            candidates = [
                value for line, value in assignments.get(child.id, []) if line < before
            ]
            if candidates:
                pending.append(candidates[-1])
    return expressions


def _named_bind_sql_additions(
    sql_node: ast.AST | None,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    before: int,
) -> tuple[set[str], dict[tuple[int, int], set[str]]] | None:
    """Resolve literal named binds appended to a list used by SQL ``join``."""
    if sql_node is None:
        return None
    expressions = _expression_assignment_closure(sql_node, assignments, before)
    join_calls = [
        item
        for expression in expressions
        for item in ast.walk(expression)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "join"
        and len(item.args) == 1
        and isinstance(item.args[0], ast.Name)
    ]
    list_joins: dict[str, list[int]] = {}
    for call in join_calls:
        list_joins.setdefault(call.args[0].id, []).append(call.lineno)
    if not list_joins:
        return set(), {}

    parents = {
        child: parent
        for parent in ast.walk(function)
        for child in ast.iter_child_nodes(parent)
    }
    unconditional_names: set[str] = set()
    conditional_names: dict[tuple[int, int], set[str]] = {}
    for list_name, join_lines in list_joins.items():
        if len(set(join_lines)) != 1:
            return None
        join_line = join_lines[0]
        candidates = [
            (line, value) for line, value in assignments.get(list_name, []) if line < join_line
        ]
        if not candidates:
            return None
        initial_line, initial_value = candidates[-1]
        if not isinstance(initial_value, (ast.List, ast.Tuple)) or _string_sequence(
            initial_value, assignments, initial_line
        ) is None:
            return None
        if any(
            isinstance(statement, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == list_name
                for target in (
                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                )
            )
            and initial_line < statement.lineno < join_line
            for statement in ast.walk(function)
        ):
            return None

        join_call_ids = {id(call) for call in join_calls if call.args[0].id == list_name}
        for statement in ast.walk(function):
            statement_line = getattr(statement, "lineno", before)
            if not initial_line < statement_line < join_line:
                continue
            if isinstance(statement, ast.AugAssign) and (
                isinstance(statement.target, ast.Name)
                and statement.target.id == list_name
                or isinstance(statement.target, ast.Subscript)
                and isinstance(statement.target.value, ast.Name)
                and statement.target.value.id == list_name
            ):
                return None
            if isinstance(statement, ast.Delete) and any(
                isinstance(target, ast.Name)
                and target.id == list_name
                or isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == list_name
                for target in statement.targets
            ):
                return None
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = statement.value
                if isinstance(value, ast.Name) and value.id == list_name:
                    return None
                targets = (
                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                )
                if any(
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == list_name
                    for target in targets
                ):
                    return None
            if isinstance(statement, ast.Attribute) and isinstance(
                statement.value, ast.Name
            ) and statement.value.id == list_name:
                parent = parents.get(statement)
                if not (
                    statement.attr == "append"
                    and isinstance(parent, ast.Call)
                    and parent.func is statement
                ):
                    return None
            if (
                isinstance(statement, ast.Call)
                and id(statement) not in join_call_ids
                and any(
                    isinstance(child, ast.Name) and child.id == list_name
                    for argument in statement.args
                    for child in ast.walk(argument)
                )
            ):
                return None

        for mutation in ast.walk(function):
            if not (
                isinstance(mutation, ast.Call)
                and isinstance(mutation.func, ast.Attribute)
                and isinstance(mutation.func.value, ast.Name)
                and mutation.func.value.id == list_name
                and initial_line < mutation.lineno < join_line
            ):
                continue
            if mutation.func.attr != "append" or len(mutation.args) != 1 or mutation.keywords:
                return None
            fragment = _string_value(mutation.args[0], assignments, mutation.lineno)
            if fragment is None:
                return None
            names = _sql_named_bind_names(fragment)
            branch = _simple_branch_path(mutation, parents)
            if branch is None:
                return None
            if branch:
                conditional_names.setdefault(branch, set()).update(names)
            else:
                unconditional_names.update(names)
    return unconditional_names, conditional_names


def _named_bind_parameter_keys(
    parameter_node: ast.AST | None,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    before: int,
) -> tuple[set[str], dict[tuple[int, int], set[str]]] | None:
    """Resolve a literal dict and simple branch-local ``params[key]`` writes."""
    parameter_name: str | None = None
    dictionary: ast.Dict | None = None
    dictionary_line = before
    if isinstance(parameter_node, ast.Dict):
        dictionary = parameter_node
    elif isinstance(parameter_node, ast.Name):
        parameter_name = parameter_node.id
        candidates = [
            (line, value) for line, value in assignments.get(parameter_name, []) if line < before
        ]
        if len(candidates) != 1 or not isinstance(candidates[0][1], ast.Dict):
            return None
        dictionary_line, dictionary = candidates[0]
    else:
        return None

    keys: set[str] = set()
    for key in dictionary.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            return None
        keys.add(key.value)

    if parameter_name is None:
        return keys, {}

    parents = {
        child: parent
        for parent in ast.walk(function)
        for child in ast.iter_child_nodes(parent)
    }
    conditional_keys: dict[tuple[int, int], set[str]] = {}
    for statement in ast.walk(function):
        if not dictionary_line < getattr(statement, "lineno", before) < before:
            continue
        targets: list[ast.AST] = []
        if isinstance(statement, ast.Assign):
            targets.extend(statement.targets)
        elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
            targets.append(statement.target)
        elif isinstance(statement, ast.Delete):
            targets.extend(statement.targets)

        for target in targets:
            if isinstance(target, ast.Name) and target.id == parameter_name:
                return None
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                if target.value.id != parameter_name:
                    continue
                if isinstance(statement, ast.Delete) or not isinstance(
                    statement, (ast.Assign, ast.AnnAssign)
                ):
                    return None
                key_node = target.slice
                if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                    return None
                branch = _simple_branch_path(statement, parents)
                if branch is None:
                    return None
                if branch:
                    conditional_keys.setdefault(branch, set()).add(key_node.value)
                else:
                    keys.add(key_node.value)

        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Name):
            if statement.value.id == parameter_name and any(
                isinstance(target, ast.Name) and target.id != parameter_name
                for target in statement.targets
            ):
                return None

        if (
            isinstance(statement, ast.Call)
            and isinstance(statement.func, ast.Attribute)
            and isinstance(statement.func.value, ast.Name)
            and statement.func.value.id == parameter_name
            and statement.func.attr not in {"copy", "get", "keys", "values", "items"}
        ):
            return None
        if isinstance(statement, ast.Call) and any(
            isinstance(child, ast.Name) and child.id == parameter_name
            for argument in statement.args
            for child in ast.walk(argument)
        ):
            return None
    return keys, conditional_keys


def _named_bind_contract(
    sql: str | None,
    sql_node: ast.AST | None,
    call: ast.Call,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    conditional_sql_variants: list[tuple[tuple[int, int], int, ast.AST]] | None = None,
) -> dict | None:
    """Compare static named SQL binds with literal mapping keys by branch."""
    if sql is None or conditional_sql_variants:
        return None
    required_base = _sql_named_bind_names(sql)
    if not required_base or _sql_bind_counts(sql)[0]:
        return None
    positional_index = 2 if isinstance(call.func, ast.Name) and call.func.id == "query" else 1
    parameter_node = call.args[positional_index] if len(call.args) > positional_index else next(
        (keyword.value for keyword in call.keywords if keyword.arg in {"params", "parameters"}),
        None,
    )
    parameter_info = _named_bind_parameter_keys(
        parameter_node, assignments, function, call.lineno
    )
    sql_additions = _named_bind_sql_additions(sql_node, assignments, function, call.lineno)
    if parameter_info is None or sql_additions is None:
        return None

    supplied_base, supplied_branches = parameter_info
    sql_unconditional, sql_branches = sql_additions
    required = required_base | sql_unconditional
    supplied = set(supplied_base)
    all_branches = set(sql_branches) | set(supplied_branches)
    variants = []
    for branch in sorted(all_branches):
        branch_required = sql_branches.get(branch, set())
        branch_supplied = supplied_branches.get(branch, set())
        effective_required = required | branch_required
        effective_supplied = supplied | branch_supplied
        mismatch = effective_required != effective_supplied
        variants.append(
            {
                "conditional_line": branch[0],
                "branch": branch[1],
                "required_names": sorted(effective_required),
                "supplied_names": sorted(effective_supplied),
                "mismatch": mismatch,
            }
        )
    base_mismatch = required != supplied
    all_required = required | (
        set().union(*sql_branches.values()) if sql_branches else set()
    )
    all_supplied = supplied | (
        set().union(*supplied_branches.values()) if supplied_branches else set()
    )
    return {
        "required_names": sorted(all_required),
        "supplied_names": sorted(all_supplied),
        "base_required_names": sorted(required),
        "base_supplied_names": sorted(supplied),
        "variants": variants,
        "mismatch": base_mismatch or any(item["mismatch"] for item in variants),
    }


def _assigned_values(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    module_tree: ast.Module | None = None,
) -> dict[str, list[tuple[int, ast.AST]]]:
    """Collect local assignments and unique literal module strings not shadowed locally."""
    assignments: dict[str, list[tuple[int, ast.AST]]] = {}
    local_names = {
        argument.arg
        for argument in [
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
            *([function.args.vararg] if function.args.vararg else []),
            *([function.args.kwarg] if function.args.kwarg else []),
        ]
    }
    local_names.update(
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    )
    if module_tree is not None:
        module_assignments: dict[str, list[tuple[int, ast.AST]]] = {}
        for statement in module_tree.body:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target = statement.targets[0]
                if isinstance(target, ast.Name):
                    module_assignments.setdefault(target.id, []).append(
                        (statement.lineno, statement.value)
                    )
            elif isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ) and statement.value is not None:
                module_assignments.setdefault(statement.target.id, []).append(
                    (statement.lineno, statement.value)
                )
        for name, values in module_assignments.items():
            if name in local_names or len(values) != 1:
                continue
            line, value = values[0]
            if line >= function.lineno:
                continue
            resolved = _string_value(value, {}, line)
            if resolved is not None:
                assignments[name] = [(line, ast.Constant(value=resolved))]

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
    include_unconditional_string_suffix: bool = False,
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
        nested_branch_writes = False
        for branch in (node.body, node.orelse):
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
            if include_unconditional_string_suffix:
                direct_lines = set()
                for statement in branch:
                    if isinstance(statement, ast.Assign) and any(
                        isinstance(target, ast.Name) and target.id == name
                        for target in statement.targets
                    ):
                        direct_lines.add(statement.lineno)
                    elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)) and isinstance(
                        statement.target, ast.Name
                    ) and statement.target.id == name:
                        direct_lines.add(statement.lineno)
                nested_branch_writes = nested_branch_writes or bool(lines - direct_lines)
            branch_lines.update(lines)
            branch_values.append(
                [(line, value) for line, value in assignments.get(name, []) if line in lines]
            )
        if not any(branch_values):
            continue
        if nested_branch_writes:
            continue
        latest_assignment = max(
            (line for line, _value in assignments.get(name, []) if line < before),
            default=-1,
        )
        post_statements: list[ast.stmt] = []
        if latest_assignment not in branch_lines:
            if not include_unconditional_string_suffix:
                continue
            statement_block = next(
                (
                    values
                    for parent in ast.walk(function)
                    for _field, values in ast.iter_fields(parent)
                    if isinstance(values, list)
                    and node in values
                    and all(isinstance(value, ast.stmt) for value in values)
                ),
                function.body,
            )
            post_lines = sorted(
                line
                for line, _value in assignments.get(name, [])
                if node.lineno < line < before and line not in branch_lines
            )
            statement_by_line = {
                statement.lineno: statement
                for statement in statement_block
                if hasattr(statement, "lineno")
            }
            if not post_lines or any(line not in statement_by_line for line in post_lines):
                continue
            post_statements = [statement_by_line[line] for line in post_lines]
            if any(
                not isinstance(statement, ast.AugAssign)
                or not isinstance(statement.target, ast.Name)
                or statement.target.id != name
                or not isinstance(statement.op, ast.Add)
                or _string_value(statement.value, assignments, statement.lineno) is None
                for statement in post_statements
            ):
                continue
        prior = [(line, value) for line, value in assignments.get(name, []) if line < node.lineno]
        for branch_index, values in enumerate(branch_values):
            if values:
                line, value = values[-1]
                if not include_unconditional_string_suffix:
                    variants.append(((node.lineno, branch_index), line, value))
                    continue
                branch_value = _string_value(value, assignments, line)
            elif prior:
                line, value = prior[-1]
                if not include_unconditional_string_suffix:
                    variants.append(((node.lineno, branch_index), line, value))
                    continue
                branch_value = _string_value(value, assignments, line)
            else:
                continue
            if branch_value is None:
                continue
            for statement in post_statements:
                suffix = _string_value(statement.value, assignments, statement.lineno)
                if suffix is None:
                    branch_value = None
                    break
                branch_value += suffix
            if branch_value is not None:
                variants.append(
                    ((node.lineno, branch_index), before, ast.Constant(value=branch_value))
                )
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


def _query_parameter_argument(call: ast.Call) -> ast.AST | None:
    offset = 2 if isinstance(call.func, ast.Name) and call.func.id == "query" else 1
    if len(call.args) > offset:
        return call.args[offset]
    return next(
        (keyword.value for keyword in call.keywords if keyword.arg in {"params", "parameters"}),
        None,
    )


def _local_query_callsite_variants(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    sql_node: ast.AST | None,
    parameter_node: ast.AST | None,
    module_tree: ast.Module | None,
) -> tuple[list[str], dict] | None:
    """Resolve a query wrapper only when every direct local call passes literals."""
    if (
        module_tree is None
        or not isinstance(sql_node, ast.Name)
        or not isinstance(parameter_node, ast.Name)
    ):
        return None
    positional_args = [*function.args.posonlyargs, *function.args.args]
    argument_names = [argument.arg for argument in positional_args]
    try:
        sql_index = argument_names.index(sql_node.id)
        parameter_index = argument_names.index(parameter_node.id)
    except ValueError:
        return None

    parents = {
        child: parent
        for parent in ast.walk(module_tree)
        for child in ast.iter_child_nodes(parent)
    }
    call_sites: list[tuple[ast.Call, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for candidate in ast.walk(module_tree):
        if not (
            isinstance(candidate, ast.Call)
            and isinstance(candidate.func, ast.Name)
            and candidate.func.id == function.name
        ):
            continue
        current: ast.AST = candidate
        caller = None
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                caller = current
                break
        if caller is None or caller is function:
            return None
        if any(
            isinstance(node, ast.Name)
            and node.id == function.name
            and isinstance(node.ctx, ast.Store)
            for node in ast.walk(caller)
        ):
            return None
        call_sites.append((candidate, caller))
    if not call_sites:
        return None

    sql_variants: list[str] = []
    variants: list[dict] = []
    for call, caller in call_sites:
        def argument_at(index: int, name: str) -> ast.AST | None:
            if len(call.args) > index:
                return call.args[index]
            return next(
                (keyword.value for keyword in call.keywords if keyword.arg == name),
                None,
            )

        actual_sql = argument_at(sql_index, sql_node.id)
        actual_parameters = argument_at(parameter_index, parameter_node.id)
        if not isinstance(actual_parameters, (ast.Tuple, ast.List)) or any(
            isinstance(item, ast.Starred) for item in actual_parameters.elts
        ):
            return None
        if not isinstance(actual_sql, ast.Constant) or not isinstance(actual_sql.value, str):
            return None
        resolved_sql = actual_sql.value
        placeholder_count, named_binds = _sql_bind_counts(resolved_sql)
        if named_binds:
            return None
        supplied_count = len(actual_parameters.elts)
        variants.append(
            {
                "call_site_line": call.lineno,
                "caller": caller.name,
                "placeholder_count": placeholder_count,
                "supplied_count": supplied_count,
                "mismatch": placeholder_count != supplied_count,
            }
        )
        sql_variants.append(resolved_sql)

    return sql_variants, {
        "mismatch": any(variant["mismatch"] for variant in variants),
        "variants": variants,
    }


def _local_formatted_query_callsite_variants(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    sql_node: ast.AST | None,
    parameter_node: ast.AST | None,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    query_call: ast.Call,
    module_tree: ast.Module | None,
) -> tuple[list[str], dict] | None:
    """Resolve f-string SQL identifiers from all literal same-module callers."""
    if module_tree is None or not isinstance(sql_node, ast.JoinedStr):
        return None
    names: list[str] = []
    for item in sql_node.values:
        if not isinstance(item, ast.FormattedValue):
            continue
        if (
            not isinstance(item.value, ast.Name)
            or item.conversion != -1
            or item.format_spec is not None
        ):
            return None
        names.append(item.value.id)
    if not names:
        return None
    positional_args = [*function.args.posonlyargs, *function.args.args]
    argument_indexes = {argument.arg: index for index, argument in enumerate(positional_args)}
    if any(name not in argument_indexes for name in names):
        return None

    parents = {
        child: parent
        for parent in ast.walk(module_tree)
        for child in ast.iter_child_nodes(parent)
    }
    call_sites: list[tuple[ast.Call, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for candidate in ast.walk(module_tree):
        if not (
            isinstance(candidate, ast.Call)
            and isinstance(candidate.func, ast.Name)
            and candidate.func.id == function.name
        ):
            continue
        current: ast.AST = candidate
        caller = None
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                caller = current
                break
        if (
            caller is None
            or caller is function
            or any(isinstance(argument, ast.Starred) for argument in candidate.args)
        ):
            return None
        if any(
            isinstance(node, ast.Name)
            and node.id == function.name
            and isinstance(node.ctx, ast.Store)
            for node in ast.walk(caller)
        ):
            return None
        call_sites.append((candidate, caller))
    if not call_sites:
        return None

    defaults_offset = len(positional_args) - len(function.args.defaults)
    sql_variants: list[str] = []
    arity_variants: list[dict] = []
    for call, caller in call_sites:
        branch_assignments = dict(assignments)
        for name in names:
            index = argument_indexes[name]
            actual = call.args[index] if len(call.args) > index else next(
                (keyword.value for keyword in call.keywords if keyword.arg == name),
                None,
            )
            if actual is None and index >= defaults_offset:
                actual = function.args.defaults[index - defaults_offset]
            if any(keyword.arg == name for keyword in call.keywords) and len(call.args) > index:
                return None
            if not isinstance(actual, ast.Constant) or not isinstance(actual.value, str):
                return None
            # The wrapper's parameter names are replaced by each caller's
            # literal before resolving the template f-string.
            branch_assignments[name] = [(-1, ast.Constant(value=actual.value))]

        resolved_sql = _string_value(sql_node, branch_assignments, function.lineno)
        if resolved_sql is None:
            return None
        placeholder_count, named_binds = _sql_bind_counts(resolved_sql)
        supplied_count = _known_parameter_count(
            parameter_node, assignments, query_call.lineno, function
        )
        if named_binds or supplied_count is None:
            return None
        sql_variants.append(resolved_sql)
        arity_variants.append(
            {
                "call_site_line": call.lineno,
                "caller": caller.name,
                "placeholder_count": placeholder_count,
                "supplied_count": supplied_count,
                "mismatch": placeholder_count != supplied_count,
            }
        )
    return sql_variants, {
        "mismatch": any(item["mismatch"] for item in arity_variants),
        "variants": arity_variants,
    }


def _list_append_state(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    before: int,
    parents: dict[ast.AST, ast.AST],
    *,
    require_string_items: bool,
) -> tuple[list[str] | int, list[tuple[tuple[tuple[int, int], ...], str | None]]] | None:
    """Resolve one local literal list plus simple append operations before a query."""
    candidates = [(line, value) for line, value in assignments.get(name, []) if line < before]
    if not candidates:
        return None
    initial_line, initial = candidates[-1]
    if not isinstance(initial, (ast.List, ast.Tuple)) or any(
        isinstance(item, ast.Starred) for item in initial.elts
    ):
        return None
    if require_string_items:
        initial_values = [
            _string_value(item, assignments, initial_line) for item in initial.elts
        ]
        if any(item is None for item in initial_values):
            return None
        initial_state: list[str] | int = [item for item in initial_values if item is not None]
    else:
        initial_state = len(initial.elts)

    mutations: list[tuple[tuple[int, int] | tuple[()], str | None]] = []
    for node in ast.walk(function):
        line = getattr(node, "lineno", -1)
        if not initial_line < line < before:
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if isinstance(value, ast.Name) and value.id == name:
                # A second reference can mutate the same list without a
                # receiver named `name`; do not claim a complete append trace.
                return None
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return None
            if any(
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == name
                for target in targets
            ):
                return None
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return None
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != name:
            continue
        if node.func.attr != "append" or len(node.args) != 1 or node.keywords:
            return None
        branch_path = _simple_branch_path(node, parents)
        if branch_path is None:
            return None
        appended_value = None
        if require_string_items:
            appended_value = _string_value(node.args[0], assignments, node.lineno)
            if appended_value is None:
                return None
        normalized_path = (branch_path,) if branch_path else ()
        mutations.append((normalized_path, appended_value))

    for reference in ast.walk(function):
        if not isinstance(reference, ast.Name) or reference.id != name:
            continue
        if not initial_line < reference.lineno < before:
            continue
        parent = parents.get(reference)
        if isinstance(parent, ast.Attribute) and parent.value is reference:
            # The call receiver is validated above and must be append().
            continue
        if require_string_items and isinstance(parent, ast.IfExp) and parent.test is reference:
            continue
        if (
            require_string_items
            and isinstance(parent, ast.Call)
            and parent.args
            and parent.args[0] is reference
            and isinstance(parent.func, ast.Attribute)
            and parent.func.attr == "join"
            and isinstance(parent.func.value, ast.Constant)
            and isinstance(parent.func.value.value, str)
        ):
            continue
        # Aliases, copies, escapes to other calls, and unexpected reads can
        # hide mutations from this deliberately narrow append trace.
        return None

    return initial_state, mutations


def _join_list_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for candidate in ast.walk(node):
        if (
            isinstance(candidate, ast.Call)
            and isinstance(candidate.func, ast.Attribute)
            and candidate.func.attr == "join"
            and isinstance(candidate.func.value, ast.Constant)
            and isinstance(candidate.func.value.value, str)
            and len(candidate.args) == 1
            and isinstance(candidate.args[0], ast.Name)
        ):
            names.add(candidate.args[0].id)
    return names


def _resolve_query_string_fragment(
    node: ast.AST,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    before: int,
    list_values: dict[str, list[str]],
    visited: frozenset[str] = frozenset(),
) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in visited:
            return None
        candidates = [(line, value) for line, value in assignments.get(node.id, []) if line < before]
        return (
            _resolve_query_string_fragment(
                candidates[-1][1], assignments, before, list_values, visited | {node.id}
            )
            if candidates
            else None
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_query_string_fragment(node.left, assignments, before, list_values, visited)
        right = _resolve_query_string_fragment(node.right, assignments, before, list_values, visited)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.IfExp) and isinstance(node.test, ast.Name):
        values = list_values.get(node.test.id)
        if values is None:
            return None
        branch = node.body if values else node.orelse
        return _resolve_query_string_fragment(branch, assignments, before, list_values, visited)
    if isinstance(node, ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
            and isinstance(node.func.value, ast.Constant)
            and isinstance(node.func.value.value, str)
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
        ):
            values = list_values.get(node.args[0].id)
            return node.func.value.value.join(values) if values is not None else None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue) and value.conversion == -1 and value.format_spec is None:
                part = _resolve_query_string_fragment(
                    value.value, assignments, before, list_values, visited
                )
                if part is None:
                    return None
                parts.append(part)
            else:
                return None
        return "".join(parts)
    return None


def _optional_filter_list_query_variants(
    sql_node: ast.AST | None,
    call: ast.Call,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[list[str], dict] | None:
    """Resolve simple optional SQL-fragment and parameter-list appends together."""
    if not isinstance(sql_node, ast.JoinedStr):
        return None
    parameter_node = _query_parameter_argument(call)
    if not isinstance(parameter_node, ast.Name):
        return None

    parents = {
        child: parent
        for parent in ast.walk(function)
        for child in ast.iter_child_nodes(parent)
    }
    sql_list_names: set[str] = set()
    for value in sql_node.values:
        if not isinstance(value, ast.FormattedValue):
            continue
        expression = value.value
        if isinstance(expression, ast.Name):
            candidates = [
                assigned
                for line, assigned in assignments.get(expression.id, [])
                if line < call.lineno
            ]
            if candidates:
                sql_list_names.update(_join_list_names(candidates[-1]))
    if len(sql_list_names) != 1:
        return None
    sql_list_name = next(iter(sql_list_names))

    sql_state = _list_append_state(
        function,
        sql_list_name,
        assignments,
        call.lineno,
        parents,
        require_string_items=True,
    )
    parameter_state = _list_append_state(
        function,
        parameter_node.id,
        assignments,
        call.lineno,
        parents,
        require_string_items=False,
    )
    if sql_state is None or parameter_state is None:
        return None
    sql_initial, sql_mutations = sql_state
    parameter_initial, parameter_mutations = parameter_state
    if not isinstance(sql_initial, list) or not isinstance(parameter_initial, int):
        return None
    if not any(path for path, _ in [*sql_mutations, *parameter_mutations]):
        return None

    guard_lines = sorted(
        {
            line
            for path, _value in [*sql_mutations, *parameter_mutations]
            for line, _branch in path
        }
    )
    if len(guard_lines) > 6:
        return None

    variants: list[dict] = []
    sql_variants: list[str] = []
    for selected_branches in product((0, 1), repeat=len(guard_lines)):
        choices = dict(zip(guard_lines, selected_branches, strict=True))

        def selected(path: tuple[tuple[int, int], ...] | tuple[()]) -> bool:
            return all(choices[line] == branch for line, branch in path)

        sql_list = list(sql_initial)
        for path, appended in sql_mutations:
            if selected(path) and appended is not None:
                sql_list.append(appended)
        parameter_count = parameter_initial + sum(
            selected(path) for path, _value in parameter_mutations
        )
        resolved_sql = _resolve_query_string_fragment(
            sql_node,
            assignments,
            call.lineno,
            {sql_list_name: sql_list},
        )
        if resolved_sql is None:
            return None
        placeholder_count, named_binds = _sql_bind_counts(resolved_sql)
        if named_binds:
            return None
        variants.append(
            {
                "conditions": [
                    {"line": line, "branch": choices[line]} for line in guard_lines
                ],
                "placeholder_count": placeholder_count,
                "supplied_count": parameter_count,
                "mismatch": placeholder_count != parameter_count,
            }
        )
        sql_variants.append(resolved_sql)

    return sql_variants, {
        "mismatch": any(variant["mismatch"] for variant in variants),
        "variants": variants,
    }


def _tuple_filter_query_variants(
    sql_node: ast.AST | None,
    call: ast.Call,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[list[str], dict] | None:
    """Resolve a fail-closed if/elif chain assigning ``(where, params)``.

    This deliberately handles only literal SQL fragments paired with literal
    positional parameter containers. It does not infer that the selected
    predicate is an authorization or tenant boundary.
    """
    if not isinstance(sql_node, ast.JoinedStr):
        return None
    parameter_node = _query_parameter_argument(call)
    if not isinstance(parameter_node, ast.Name):
        return None
    formatted_names = [
        item.value.id
        for item in sql_node.values
        if isinstance(item, ast.FormattedValue) and isinstance(item.value, ast.Name)
    ]
    if len(formatted_names) != 1 or sum(
        isinstance(item, ast.FormattedValue) for item in sql_node.values
    ) != 1:
        return None
    where_name = formatted_names[0]

    def literal_pair(body: list[ast.stmt]) -> tuple[str, list | tuple, ast.Assign] | None:
        if len(body) != 1 or not isinstance(body[0], ast.Assign):
            return None
        assignment = body[0]
        if (
            len(assignment.targets) != 1
            or not isinstance(assignment.targets[0], ast.Tuple)
            or len(assignment.targets[0].elts) != 2
            or not all(isinstance(item, ast.Name) for item in assignment.targets[0].elts)
            or [item.id for item in assignment.targets[0].elts]
            != [where_name, parameter_node.id]
            or not isinstance(assignment.value, ast.Tuple)
            or len(assignment.value.elts) != 2
        ):
            return None
        fragment, values = assignment.value.elts
        if not isinstance(fragment, ast.Constant) or not isinstance(fragment.value, str):
            return None
        if not isinstance(values, (ast.List, ast.Tuple)) or any(
            isinstance(item, ast.Starred) for item in values.elts
        ):
            return None
        return fragment.value, values.elts, assignment

    def is_single_raise(body: list[ast.stmt]) -> bool:
        return len(body) == 1 and isinstance(body[0], ast.Raise)

    def collect_chain(
        node: ast.If,
    ) -> list[tuple[str, list | tuple, ast.Assign, int]] | None:
        pair = literal_pair(node.body)
        if pair is None:
            return None
        variants = [(*pair, node.lineno)]
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            following = collect_chain(node.orelse[0])
            return variants + following if following else None
        if not is_single_raise(node.orelse):
            return None
        return variants

    candidate_chains = [
        variants
        for statement in function.body
        if isinstance(statement, ast.If) and statement.lineno < call.lineno
        and (variants := collect_chain(statement)) is not None
    ]
    if len(candidate_chains) != 1:
        return None
    branch_values = candidate_chains[0]
    paired_assignments = {
        id(assignment)
        for _fragment, _values, assignment, _condition_line in branch_values
    }
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        written_names = {
            child.id
            for target in targets
            for child in ast.walk(target)
            if isinstance(child, ast.Name)
        }
        if (
            node.lineno < call.lineno
            and written_names.intersection({where_name, parameter_node.id})
            and id(node) not in paired_assignments
        ):
            return None

    sql_variants: list[str] = []
    arity_variants: list[dict] = []
    for branch, (fragment, values, assignment, condition_line) in enumerate(branch_values):
        branch_assignments = dict(assignments)
        branch_assignments[where_name] = [
            (assignment.lineno, ast.Constant(value=fragment))
        ]
        resolved_sql = _string_value(sql_node, branch_assignments, call.lineno)
        if resolved_sql is None:
            return None
        placeholder_count, named_binds = _sql_bind_counts(resolved_sql)
        if named_binds:
            return None
        supplied_count = len(values)
        arity_variants.append(
            {
                "conditional_line": condition_line,
                "branch": branch,
                "placeholder_count": placeholder_count,
                "supplied_count": supplied_count,
                "mismatch": placeholder_count != supplied_count,
            }
        )
        sql_variants.append(resolved_sql)
    return sql_variants, {
        "mismatch": any(item["mismatch"] for item in arity_variants),
        "variants": arity_variants,
    }


def _local_helper_filter_query_variants(
    sql_node: ast.AST | None,
    call: ast.Call,
    assignments: dict[str, list[tuple[int, ast.AST]]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    module_tree: ast.Module | None,
) -> tuple[list[str], dict, list[dict]] | None:
    """Resolve tuple filters returned by a small same-module helper.

    Every normal helper exit must return a literal SQL fragment paired with a
    literal list/tuple of positional binds; every other path must raise. The
    result checks SQL/bind arity and a narrow location-scope source signal when
    a returned location predicate binds the caller's ``location_id`` argument.
    This does not establish authorization.
    """
    if module_tree is None or not isinstance(sql_node, ast.JoinedStr):
        return None
    parameter_node = _query_parameter_argument(call)
    if not isinstance(parameter_node, ast.Name):
        return None
    formatted_names = [
        item.value.id
        for item in sql_node.values
        if isinstance(item, ast.FormattedValue) and isinstance(item.value, ast.Name)
    ]
    if len(formatted_names) != 1 or sum(
        isinstance(item, ast.FormattedValue) for item in sql_node.values
    ) != 1:
        return None
    where_name = formatted_names[0]

    assignments_to_pair = []
    helper_call: ast.Call | None = None
    helper_name: str | None = None
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (
            isinstance(target, ast.Tuple)
            and len(target.elts) == 2
            and all(isinstance(item, ast.Name) for item in target.elts)
            and [item.id for item in target.elts] == [where_name, parameter_node.id]
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.lineno < call.lineno
        ):
            continue
        assignments_to_pair.append(node)
        helper_call = node.value
        helper_name = node.value.func.id
    if len(assignments_to_pair) != 1 or helper_call is None or helper_name is None:
        return None
    pair_assignment = assignments_to_pair[0]
    if any(
        isinstance(node, ast.Name)
        and node.id == helper_name
        and isinstance(node.ctx, ast.Store)
        for node in ast.walk(function)
    ):
        return None
    for node in ast.walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            written = {
                child.id
                for target in targets
                for child in ast.walk(target)
                if isinstance(child, ast.Name)
            }
            if (
                node.lineno < call.lineno
                and written.intersection({where_name, parameter_node.id})
                and node is not pair_assignment
            ):
                return None

    helper_definitions = [
        node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == helper_name
    ]
    if len(helper_definitions) != 1:
        return None
    helper = helper_definitions[0]

    def return_pair(statement: ast.Return) -> tuple[str, list[ast.expr], int] | None:
        value = statement.value
        if not isinstance(value, ast.Tuple) or len(value.elts) != 2:
            return None
        fragment, values = value.elts
        if not isinstance(fragment, ast.Constant) or not isinstance(fragment.value, str):
            return None
        if not isinstance(values, (ast.List, ast.Tuple)) or any(
            isinstance(item, ast.Starred) for item in values.elts
        ):
            return None
        return fragment.value, list(values.elts), statement.lineno

    def analyze_exits(
        statements: list[ast.stmt],
    ) -> tuple[list[tuple[str, list[ast.expr], int]], bool] | None:
        returned: list[tuple[str, list[ast.expr], int]] = []
        falls_through = True
        for statement in statements:
            if not falls_through:
                break
            if isinstance(statement, ast.Return):
                pair = return_pair(statement)
                if pair is None:
                    return None
                returned.append(pair)
                falls_through = False
            elif isinstance(statement, ast.Raise):
                falls_through = False
            elif isinstance(statement, ast.If):
                body = analyze_exits(statement.body)
                otherwise = analyze_exits(statement.orelse)
                if body is None or otherwise is None:
                    return None
                returned.extend(body[0])
                returned.extend(otherwise[0])
                falls_through = body[1] or otherwise[1]
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                body = analyze_exits(statement.body)
                if body is None:
                    return None
                returned.extend(body[0])
                falls_through = body[1]
            elif isinstance(
                statement,
                (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Pass, ast.Assert),
            ):
                continue
            else:
                return None
        return returned, falls_through

    exit_summary = analyze_exits(helper.body)
    if exit_summary is None or exit_summary[1] or not exit_summary[0]:
        return None

    helper_positional = [*helper.args.posonlyargs, *helper.args.args]
    call_arguments: dict[str, ast.expr] = {}
    if not helper.args.vararg and not helper.args.kwarg:
        if len(helper_call.args) <= len(helper_positional) and not any(
            isinstance(argument, ast.Starred) for argument in helper_call.args
        ):
            call_arguments = {
                argument.arg: value
                for argument, value in zip(helper_positional, helper_call.args)
            }
            for keyword in helper_call.keywords:
                if keyword.arg is None or keyword.arg in call_arguments:
                    call_arguments = {}
                    break
                call_arguments[keyword.arg] = keyword.value

    caller_has_location_argument = any(
        argument.arg == "location_id"
        for argument in [
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        ]
    )
    sql_variants: list[str] = []
    arity_variants: list[dict] = []
    location_scope_variants: list[dict] = []
    for fragment, bind_values, return_line in exit_summary[0]:
        branch_assignments = dict(assignments)
        branch_assignments[where_name] = [
            (pair_assignment.lineno, ast.Constant(value=fragment))
        ]
        resolved_sql = _string_value(sql_node, branch_assignments, call.lineno)
        if resolved_sql is None:
            return None
        placeholder_count, named_binds = _sql_bind_counts(resolved_sql)
        if named_binds:
            return None
        supplied_count = len(bind_values)
        arity_variants.append(
            {
                "helper_return_line": return_line,
                "placeholder_count": placeholder_count,
                "supplied_count": supplied_count,
                "mismatch": placeholder_count != supplied_count,
            }
        )
        sql_variants.append(resolved_sql)
        location_bound = False
        if caller_has_location_argument and len(bind_values) == 1:
            helper_value = bind_values[0]
            if isinstance(helper_value, ast.Name):
                caller_value = call_arguments.get(helper_value.id)
                location_bound = (
                    isinstance(caller_value, ast.Name)
                    and caller_value.id == "location_id"
                )
        fragment_has_location_predicate = bool(_LOCATION_PREDICATE.search(fragment))
        joined_location_aliases = set(_LOCATION_JOIN_ALIAS.findall(resolved_sql))
        joined_id_match = _JOINED_LOCATION_ID_PREDICATE.search(fragment)
        joined_location_predicate = bool(
            joined_id_match and joined_id_match.group(1).lower() in joined_location_aliases
        )
        location_scope_variants.append(
            {
                "helper_return_line": return_line,
                "location_predicate_visible": (
                    fragment_has_location_predicate or joined_location_predicate
                ),
                "location_id_bound": location_bound,
                "bound_location_scope_signal": (
                    placeholder_count == supplied_count == 1
                    and location_bound
                    and (fragment_has_location_predicate or joined_location_predicate)
                ),
            }
        )
    return sql_variants, {
        "mismatch": any(item["mismatch"] for item in arity_variants),
        "variants": arity_variants,
    }, location_scope_variants


def _query_calls(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    module_tree: ast.Module | None = None,
) -> list[dict]:
    assignments = _assigned_values(function, module_tree)
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
                function,
                sql_node.id,
                assignments,
                node.lineno,
                include_unconditional_string_suffix=True,
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
        optional_filter_variants = _optional_filter_list_query_variants(
            sql_node, node, assignments, function
        )
        tuple_filter_variants = _tuple_filter_query_variants(
            sql_node, node, assignments, function
        )
        local_helper_filter_variants = _local_helper_filter_query_variants(
            sql_node, node, assignments, function, module_tree
        )
        local_helper_scope_variants: list[dict] = []
        callsite_variants = None
        formatted_callsite_variants = None
        if optional_filter_variants:
            sql_variants, positional_arity = optional_filter_variants
            sql = sql_variants[-1]
            sql_variant_paths = [(None, value) for value in sql_variants]
        elif tuple_filter_variants:
            sql_variants, positional_arity = tuple_filter_variants
            sql = sql_variants[-1]
            sql_variant_paths = [(None, value) for value in sql_variants]
        elif local_helper_filter_variants:
            sql_variants, positional_arity, local_helper_scope_variants = (
                local_helper_filter_variants
            )
            sql = sql_variants[-1]
            sql_variant_paths = [(None, value) for value in sql_variants]
        else:
            if sql is None:
                callsite_variants = _local_query_callsite_variants(
                    function,
                    sql_node,
                    _query_parameter_argument(node),
                    module_tree,
                )
                if not callsite_variants:
                    formatted_callsite_variants = _local_formatted_query_callsite_variants(
                        function,
                        sql_node,
                        _query_parameter_argument(node),
                        assignments,
                        node,
                        module_tree,
                    )
            if callsite_variants:
                sql_variants, positional_arity = callsite_variants
                sql = sql_variants[-1]
                sql_variant_paths = [(None, value) for value in sql_variants]
            elif formatted_callsite_variants:
                sql_variants, positional_arity = formatted_callsite_variants
                sql = sql_variants[-1]
                sql_variant_paths = [(None, value) for value in sql_variants]
            else:
                positional_arity = _positional_bind_arity(
                    sql,
                    node,
                    assignments,
                    function,
                    conditional_sql_variants or None,
                )
        named_bind_contract = _named_bind_contract(
            sql,
            sql_node,
            node,
            assignments,
            function,
            conditional_sql_variants or None,
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
        if local_helper_scope_variants:
            location_predicate = location_predicate or any(
                item["location_predicate_visible"] for item in local_helper_scope_variants
            )
        location_row_lookup = any(
            _LOCATION_ROW_LOOKUP.search(query_sql) for query_sql in resolved_sql_variants
        )
        indirect_location_scope = any(
            pattern.search(query_sql)
            for pattern in _INDIRECT_LOCATION_SCOPE
            for query_sql in resolved_sql_variants
        )
        location_bound = params_include_location or any(
            item["location_id_bound"] for item in local_helper_scope_variants
        )
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
        if (
            optional_filter_variants
            or tuple_filter_variants
            or callsite_variants
            or formatted_callsite_variants
        ):
            # These source resolvers check SQL and bind shapes but do not
            # certify tenant-scope correlation.
            correlated_location_binding = False
        elif local_helper_filter_variants:
            correlated_location_binding = any(
                item["bound_location_scope_signal"]
                for item in local_helper_scope_variants
            )
        location_scope_conditionally_added = bool(conditional_sql_variants)
        if local_helper_scope_variants:
            location_variant_signals = [
                item["bound_location_scope_signal"]
                for item in local_helper_scope_variants
            ]
            location_scope_conditionally_added = location_scope_conditionally_added or (
                any(location_variant_signals) and not all(location_variant_signals)
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
                "location_scope_conditionally_added": location_scope_conditionally_added,
                "bound_location_scope_signal": location_bound
                and (location_predicate or location_row_lookup or indirect_location_scope)
                and correlated_location_binding,
                **(
                    {"location_scope_variants": local_helper_scope_variants}
                    if local_helper_scope_variants
                    else {}
                ),
                "positional_bind_arity": positional_arity,
                "named_bind_contract": named_bind_contract,
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


def _analyze_function(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    module_tree: ast.Module | None = None,
) -> dict:
    queries = _query_calls(function, module_tree)
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
        "static_named_bind_contract_site_count": sum(
            query["named_bind_contract"] is not None for query in queries
        ),
        "named_bind_contract_mismatch_count": sum(
            query["named_bind_contract"] is not None
            and query["named_bind_contract"]["mismatch"]
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
    return _analyze_function(function, tree)


def build_inventory() -> dict:
    source_inventory = build_inventory_source()
    entries = []
    classification_counts: dict[str, int] = {}
    total_queries = 0
    static_positional_arity_sites = 0
    positional_arity_mismatches = 0
    static_named_bind_contract_sites = 0
    named_bind_contract_mismatches = 0
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
        analysis = _analyze_function(function, tree)
        classification_counts[analysis["classification"]] = (
            classification_counts.get(analysis["classification"], 0) + 1
        )
        total_queries += analysis["direct_query_count"]
        static_positional_arity_sites += analysis["static_positional_arity_site_count"]
        positional_arity_mismatches += analysis["positional_arity_mismatch_count"]
        static_named_bind_contract_sites += analysis["static_named_bind_contract_site_count"]
        named_bind_contract_mismatches += analysis["named_bind_contract_mismatch_count"]
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
            "Location-dependent SQL assignment branches retain statically resolved variants, including a simple "
            "unconditional static string suffix after the branch. Positional bind arity is compared for static SQL "
            "and branch-correlated SQL when parameter counts are statically known. Unique, unshadowed module-level "
            "literal strings are resolved in SQL expressions; computed or reassigned module values remain unresolved. "
            "Named-bind keys are compared "
            "when literal mappings and simple branch-correlated condition-list appends are statically available; "
            "dynamic containers and nested conditional mutations remain unresolved. "
            "Literal same-module helper-return filters emit a branch signal only when a returned location predicate binds the caller's location_id argument. "
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
            "static_named_bind_contract_sites": static_named_bind_contract_sites,
            "named_bind_contract_mismatch_sites": named_bind_contract_mismatches,
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
