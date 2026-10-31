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
_SQL_RELATION = r'((?:"[^"\n]+"|[A-Za-z_][\w$]*)(?:\s*\.\s*(?:"[^"\n]+"|[A-Za-z_][\w$]*))?)'
_TRUNCATE_TARGETS = re.compile(
    r"^\s*(?:--[^\n]*\n\s*)*TRUNCATE\s+(?:TABLE\s+)?(?:ONLY\s+)?"
    r"(?P<targets>.+?)\s*(?:\s+(?:RESTART|CONTINUE|CASCADE|RESTRICT)\b|;?\s*$)",
    re.IGNORECASE | re.DOTALL,
)
_WRITE_TARGET_PATTERNS = {
    "INSERT": re.compile(
        r"^\s*(?:--[^\n]*\n\s*)*INSERT\s+INTO\s+(?:ONLY\s+)?"
        + _SQL_RELATION,
        re.IGNORECASE,
    ),
    "UPDATE": re.compile(
        r"^\s*(?:--[^\n]*\n\s*)*UPDATE\s+(?:ONLY\s+)?" + _SQL_RELATION,
        re.IGNORECASE,
    ),
    "DELETE": re.compile(
        r"^\s*(?:--[^\n]*\n\s*)*DELETE\s+FROM\s+(?:ONLY\s+)?"
        + _SQL_RELATION,
        re.IGNORECASE,
    ),
    "MERGE": re.compile(
        r"^\s*(?:--[^\n]*\n\s*)*MERGE\s+INTO\s+" + _SQL_RELATION,
        re.IGNORECASE,
    ),
}


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


def _write_target_relations(query: str, statement_kind: str) -> list[str]:
    """Extract simple leading mutation targets, not tables read by the query."""
    if statement_kind == "TRUNCATE":
        match = _TRUNCATE_TARGETS.match(query)
        if match is None:
            return []
        target_clause = match.group("targets").strip().rstrip(";").strip()
        parts = []
        current = []
        in_identifier = False
        for character in target_clause:
            if character == '"':
                in_identifier = not in_identifier
            if character == "," and not in_identifier:
                parts.append("".join(current))
                current = []
            else:
                current.append(character)
        parts.append("".join(current))
        targets = []
        for part in parts:
            target_match = re.fullmatch(
                r"\s*" + _SQL_RELATION + r"\s*\*?\s*", part
            )
            if target_match is None:
                return []
            target = re.sub(r"\s*\.\s*", ".", target_match.group(1))
            targets.append(target.replace('"', ""))
        return sorted(set(targets))
    pattern = _WRITE_TARGET_PATTERNS.get(statement_kind)
    if pattern is None:
        return []
    match = pattern.match(query)
    if match is None:
        return []
    relation = re.sub(r"\s*\.\s*", ".", match.group(1)).replace('"', "")
    return [relation]


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


def _operation_map_variants(
    tree: ast.Module, function: ast.FunctionDef | ast.AsyncFunctionDef, name: str
) -> list[dict] | None:
    """Resolve a local SQL variable returned by a guarded immutable SQL map.

    This is deliberately narrow: it accepts a single local assignment from a
    helper that returns ``IMMUTABLE_MAP[operation]`` and whose map values are
    module-level literal SQL constants. It records hashes and statement
    metadata only, never SQL text or runtime parameter values.
    """
    parameters = [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
    if function.args.vararg:
        parameters.append(function.args.vararg)
    if function.args.kwarg:
        parameters.append(function.args.kwarg)
    if any(parameter.arg == name for parameter in parameters):
        return None

    local_values: list[ast.AST] = []
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                local_values.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            if node.value is not None:
                local_values.append(node.value)
        elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name) and node.target.id == name:
            local_values.append(node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and _target_binds_name(node.target, name):
            return None
        elif isinstance(node, (ast.With, ast.AsyncWith)) and any(
            item.optional_vars and _target_binds_name(item.optional_vars, name) for item in node.items
        ):
            return None
        elif isinstance(node, ast.AugAssign) and _target_binds_name(node.target, name):
            return None
        elif isinstance(node, ast.ExceptHandler) and node.name == name:
            return None
        pending.extend(ast.iter_child_nodes(node))

    if len(local_values) != 1:
        return None
    assignment = local_values[0]
    if not (
        isinstance(assignment, ast.Call)
        and isinstance(assignment.func, ast.Name)
        and len(assignment.args) == 1
        and isinstance(assignment.args[0], ast.Name)
    ):
        return None
    resolver_name = assignment.func.id
    resolver = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == resolver_name
        ),
        None,
    )
    if resolver is None:
        return None
    return_values = [node.value for node in ast.walk(resolver) if isinstance(node, ast.Return) and node.value]
    if len(return_values) != 1 or not isinstance(return_values[0], ast.Subscript):
        return None
    mapping_name = return_values[0].value
    if not isinstance(mapping_name, ast.Name):
        return None
    resolver_parameters = {
        parameter.arg
        for parameter in [*resolver.args.posonlyargs, *resolver.args.args, *resolver.args.kwonlyargs]
    }
    if resolver.args.vararg:
        resolver_parameters.add(resolver.args.vararg.arg)
    if resolver.args.kwarg:
        resolver_parameters.add(resolver.args.kwarg.arg)
    index = return_values[0].slice
    if not isinstance(index, ast.Name) or index.id not in resolver_parameters:
        return None

    proxy_imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "types"
        and any(
            alias.name == "MappingProxyType" and (alias.asname or alias.name) == "MappingProxyType"
            for alias in node.names
        )
        for node in tree.body
    )
    if not proxy_imported:
        return None

    mapping_assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == mapping_name.id for target in node.targets)
    ]
    if len(mapping_assignments) != 1:
        return None
    mapping_assignment = mapping_assignments[0]
    mapping_call = mapping_assignment.value
    if not (
        isinstance(mapping_call, ast.Call)
        and isinstance(mapping_call.func, ast.Name)
        and mapping_call.func.id == "MappingProxyType"
        and len(mapping_call.args) == 1
        and isinstance(mapping_call.args[0], ast.Dict)
    ):
        return None

    assignments_by_name: dict[str, list[ast.AST]] = defaultdict(list)
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    assignments_by_name[target.id].append(statement.value)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.value is not None:
                assignments_by_name[statement.target.id].append(statement.value)

    constants: dict[str, str] = {}
    for constant_name, assignments in assignments_by_name.items():
        if len(assignments) != 1:
            continue
        query, kind = _query_template(assignments[0])
        if kind == "literal" and query.strip():
            constants[constant_name] = query

    variants = []
    entries = zip(mapping_call.args[0].keys, mapping_call.args[0].values)
    seen_operations = set()
    for key_node, value_node in entries:
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            return None
        if key_node.value in seen_operations:
            return None
        seen_operations.add(key_node.value)
        if isinstance(value_node, ast.Name):
            query = constants.get(value_node.id)
        elif isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            query = value_node.value
        else:
            return None
        if not query:
            return None
        normalized = _normalized_query(query)
        variants.append(
            {
                "operation": key_node.value,
                "statement_kind": _statement_kind(query),
                "candidate_relations": _candidate_relations(query),
                "static_sql_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            }
        )
    return sorted(variants, key=lambda item: item["operation"]) if variants else None


def _literal_caller_variants(
    tree: ast.Module, function: ast.FunctionDef | ast.AsyncFunctionDef, name: str
) -> list[dict] | None:
    """Resolve a helper query supplied as a literal by same-module callers.

    Positional calls are accepted only when the helper signature and Python
    method binding determine the argument exactly. Dynamic values,
    reassignment, starred arguments, and missing local call contracts remain
    unresolved. Instance-method calls are followed only within their class.
    """
    parameters = [*function.args.posonlyargs, *function.args.args]
    parameter_index = next(
        (index for index, parameter in enumerate(parameters) if parameter.arg == name),
        None,
    )
    keyword_only_parameter = any(parameter.arg == name for parameter in function.args.kwonlyargs)
    if parameter_index is None and not keyword_only_parameter:
        return None

    def enclosing_class(target: ast.FunctionDef | ast.AsyncFunctionDef):
        return next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and target in node.body
            ),
            None,
        )

    helper_class = enclosing_class(function)
    is_staticmethod = helper_class is not None and any(
        isinstance(decorator, ast.Name) and decorator.id == "staticmethod"
        or isinstance(decorator, ast.Attribute) and decorator.attr == "staticmethod"
        for decorator in function.decorator_list
    )

    calls_by_function: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.Call]] = []

    class _DirectCallCollector(ast.NodeVisitor):
        def __init__(self, callee_name: str, receiver_name: str | None):
            self.callee_name = callee_name
            self.receiver_name = receiver_name
            self.calls: list[ast.Call] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            direct_call = isinstance(node.func, ast.Name) and node.func.id == self.callee_name
            instance_call = (
                self.receiver_name is not None
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == self.callee_name
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == self.receiver_name
            )
            if direct_call or instance_call:
                self.calls.append(node)
            self.generic_visit(node)

    for caller in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        caller_class = enclosing_class(caller)
        caller_parameters = [*caller.args.posonlyargs, *caller.args.args]
        receiver_name = None
        if (
            helper_class is not None
            and caller_class is helper_class
            and caller_parameters
            and caller_parameters[0].arg in {"self", "cls"}
        ):
            receiver_name = caller_parameters[0].arg
        collector = _DirectCallCollector(function.name, receiver_name)
        for statement in caller.body:
            collector.visit(statement)
        calls_by_function.extend((caller, call) for call in collector.calls)

    if not calls_by_function:
        return None

    variants = []
    for caller, call in calls_by_function:
        keyword_values = [keyword.value for keyword in call.keywords if keyword.arg == name]
        if len(keyword_values) > 1:
            return None
        if keyword_values:
            query_argument = keyword_values[0]
        else:
            if parameter_index is None:
                return None
            positional_index = parameter_index
            if isinstance(call.func, ast.Attribute) and not is_staticmethod:
                positional_index -= 1
            if positional_index < 0 or any(
                isinstance(argument, ast.Starred) for argument in call.args[: positional_index + 1]
            ):
                return None
            if positional_index >= len(call.args):
                return None
            query_argument = call.args[positional_index]

        if isinstance(query_argument, ast.Name):
            local_name = query_argument.id
            local_values: list[ast.AST] = []
            pending = list(caller.body)
            while pending:
                node = pending.pop()
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                if isinstance(node, ast.Assign):
                    if any(isinstance(target, ast.Name) and target.id == local_name for target in node.targets):
                        local_values.append(node.value)
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == local_name:
                    if node.value is not None:
                        local_values.append(node.value)
                elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name) and node.target.id == local_name:
                    local_values.append(node.value)
                elif isinstance(node, (ast.For, ast.AsyncFor)) and _target_binds_name(node.target, local_name):
                    return None
                elif isinstance(node, (ast.With, ast.AsyncWith)) and any(
                    item.optional_vars and _target_binds_name(item.optional_vars, local_name) for item in node.items
                ):
                    return None
                elif isinstance(node, ast.AugAssign) and _target_binds_name(node.target, local_name):
                    return None
                elif isinstance(node, ast.ExceptHandler) and node.name == local_name:
                    return None
                pending.extend(ast.iter_child_nodes(node))
            if len(local_values) != 1:
                return None
            query_argument = local_values[0]

        query, kind = _query_template(query_argument)
        if kind != "literal" or not query.strip():
            return None
        normalized = _normalized_query(query)
        variants.append(
            {
                "operation": f"{caller.name}@{call.lineno}",
                "statement_kind": _statement_kind(query),
                "candidate_relations": _candidate_relations(query),
                "static_sql_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            }
        )
    return sorted(variants, key=lambda item: item["operation"])


def _target_binds_name(target: ast.expr, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_target_binds_name(element, name) for element in target.elts)
    return False


class _SQLCallVisitor(ast.NodeVisitor):
    def __init__(
        self,
        source: str,
        operations: list[str],
        tree: ast.Module,
        *,
        include_write_targets: bool = False,
    ):
        self.source = source
        self.operations = operations
        self.tree = tree
        self.include_write_targets = include_write_targets
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
        statement_variants = None
        if statement_kind == "UNKNOWN" and isinstance(query_node, ast.Name) and self.functions:
            statement_kind = _local_statement_kind(self.functions[-1], query_node.id)
            if statement_kind == "UNKNOWN":
                statement_variants = _operation_map_variants(
                    self.tree, self.functions[-1], query_node.id
                )
            if statement_kind == "UNKNOWN" and not statement_variants:
                statement_variants = _literal_caller_variants(
                    self.tree, self.functions[-1], query_node.id
                )
            if statement_variants:
                kinds = {variant["statement_kind"] for variant in statement_variants}
                if len(kinds) == 1:
                    statement_kind = next(iter(kinds))
        fingerprint = None
        if expression_kind == "literal" and normalized:
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        site = {
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
        if self.include_write_targets:
            site["write_target_relations"] = _write_target_relations(
                query, statement_kind
            )
        if statement_variants:
            site["statement_variants"] = statement_variants
        return site


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
        visitor = _SQLCallVisitor(source, sorted(operation_refs), tree)
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
