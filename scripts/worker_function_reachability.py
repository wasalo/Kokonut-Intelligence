#!/usr/bin/env python3
"""Build a conservative direct-call graph for allowlisted worker operations.

The graph follows statically resolved Python function calls within each
operation's local ``services.*`` import closure. It is a review index, not a
complete runtime call graph, effect proof, authorization policy, or tenant
boundary. Dynamic dispatch, callbacks, methods on unknown instances, extension
code, and database/provider-side behavior may not be represented.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.worker_source_closure as worker_source_closure  # noqa: E402


def _function_key(module: str, qualname: str) -> str:
    return f"{module}:{qualname}"


class _DefinitionVisitor(ast.NodeVisitor):
    def __init__(self, module: str, source: str):
        self.module = module
        self.source = source
        self.scope: list[str] = []
        self.class_scope: list[str] = []
        self.definitions: dict[str, dict] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.class_scope.append(node.name)
        self.generic_visit(node)
        self.class_scope.pop()
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualname = ".".join([*self.scope, node.name])
        key = _function_key(self.module, qualname)
        self.definitions[key] = {
            "key": key,
            "module": self.module,
            "qualname": qualname,
            "class_scope": ".".join(self.class_scope) if self.class_scope else None,
            "source": self.source,
            "line": node.lineno,
            "node": node,
        }
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


class _ImportContextVisitor(ast.NodeVisitor):
    def __init__(self, module: str, source: str, known_modules: set[str], definitions: dict[str, dict]):
        self.module = module
        self.source = ROOT / source
        self.known_modules = known_modules
        self.definitions = definitions
        self.module_aliases: dict[str, str] = {}
        self.symbol_aliases: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname:
                self.module_aliases[alias.asname] = alias.name
            else:
                self.module_aliases[alias.name.split(".", 1)[0]] = alias.name.split(".", 1)[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = worker_source_closure._resolve_import_from(self.module, self.source, node)
        if not base:
            return
        for alias in node.names:
            local_name = alias.asname or alias.name
            if alias.name == "*":
                continue
            imported_function = _function_key(base, alias.name)
            imported_module = f"{base}.{alias.name}"
            if imported_function in self.definitions:
                self.symbol_aliases[local_name] = imported_function
            elif imported_module in self.known_modules:
                self.module_aliases[local_name] = imported_module


def _collect_modules(source_files: list[str]) -> tuple[dict[str, ast.Module], dict[str, str]]:
    trees = {}
    modules_by_source = {}
    for source in source_files:
        path = ROOT / source
        module = worker_source_closure._module_for_path(path)
        modules_by_source[source] = module
        try:
            trees[module] = ast.parse(path.read_text(encoding="utf-8"), filename=source)
        except (OSError, SyntaxError) as exc:
            raise ValueError(f"Unable to parse worker source {source}") from exc
    return trees, modules_by_source


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _resolve_module_call(imported_module: str, suffix: str, definitions: dict[str, dict]) -> str | None:
    parts = suffix.split(".")
    for module_part_count in range(len(parts), 0, -1):
        module = ".".join([imported_module, *parts[:module_part_count]])
        qualname = ".".join(parts[module_part_count:])
        candidate = _function_key(module, qualname) if qualname else ""
        if candidate in definitions:
            return candidate
    candidate = _function_key(imported_module, suffix)
    return candidate if candidate in definitions else None


def _resolve_call_target(
    function: dict,
    call: ast.Call,
    definitions: dict[str, dict],
    import_contexts: dict[str, _ImportContextVisitor],
) -> str | None:
    module = function["module"]
    qualname = function["qualname"]
    context = import_contexts[module]
    expression = _dotted_name(call.func)
    if not expression:
        return None

    if isinstance(call.func, ast.Name):
        imported = context.symbol_aliases.get(expression)
        if imported in definitions:
            return imported
        local = _function_key(module, expression)
        if local in definitions:
            return local
        parent = qualname.rpartition(".")[0]
        while parent:
            nested = _function_key(module, f"{parent}.{expression}")
            if nested in definitions:
                return nested
            parent = parent.rpartition(".")[0]
        return None

    prefix, separator, suffix = expression.partition(".")
    if not separator:
        return None

    if prefix in {"self", "cls"}:
        class_name = function.get("class_scope")
        candidate = _function_key(module, f"{class_name}.{suffix}") if class_name else ""
        return candidate if candidate in definitions else None

    imported = context.symbol_aliases.get(prefix)
    if imported:
        candidate = f"{imported}.{suffix}"
        return candidate if candidate in definitions else None

    imported_module = context.module_aliases.get(prefix)
    if imported_module:
        return _resolve_module_call(imported_module, suffix, definitions)

    candidate = _function_key(module, expression)
    return candidate if candidate in definitions else None


class _CallVisitor(ast.NodeVisitor):
    def __init__(self, function: dict, definitions: dict[str, dict], contexts: dict[str, _ImportContextVisitor]):
        self.function = function
        self.definitions = definitions
        self.contexts = contexts
        self.edges: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.function["node"]:
            for statement in node.body:
                self.visit(statement)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        target = _resolve_call_target(self.function, node, self.definitions, self.contexts)
        if target:
            self.edges.append(
                {
                    "caller": self.function["key"],
                    "callee": target,
                    "source": self.function["source"],
                    "line": node.lineno,
                }
            )
        self.generic_visit(node)


def _is_main_guard(test: ast.expr) -> bool:
    return isinstance(test, ast.Compare) and (
        isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and any(
            isinstance(comparator, ast.Constant) and comparator.value == "__main__" for comparator in test.comparators
        )
    )


class _RootCallVisitor(ast.NodeVisitor):
    def __init__(self, module: str, contexts: dict[str, _ImportContextVisitor], definitions: dict[str, dict]):
        self.module = module
        self.contexts = contexts
        self.definitions = definitions
        self.calls: list[tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        synthetic = {"module": self.module, "qualname": ""}
        target = _resolve_call_target(synthetic, node, self.definitions, self.contexts)
        if target:
            self.calls.append((target, node.lineno))
        self.generic_visit(node)


def _operation_roots(
    operation: dict,
    modules_by_source: dict[str, str],
    trees: dict[str, ast.Module],
    contexts: dict[str, _ImportContextVisitor],
    definitions: dict[str, dict],
) -> list[dict]:
    if operation["kind"] == "event_handler":
        module, _, function = operation["name"].rpartition(".")
        key = _function_key(module, function)
        return (
            [{"function": key, "source": definitions[key]["source"], "line": definitions[key]["line"]}]
            if key in definitions
            else []
        )

    root_module = operation["root_modules"][0]
    root_paths = worker_source_closure._module_paths(root_module)
    package_main = next((path for path in root_paths if path.name == "__main__.py"), None)
    executed_path = package_main or next((path for path in root_paths if path.name != "__init__.py"), None)
    if executed_path is None:
        return []
    source = executed_path.relative_to(ROOT).as_posix()
    module = modules_by_source.get(source)
    if not module:
        return []

    roots = []
    tree = trees[module]
    for statement in tree.body:
        if isinstance(statement, ast.If) and _is_main_guard(statement.test):
            visitor = _RootCallVisitor(module, contexts, definitions)
            for guarded_statement in statement.body:
                visitor.visit(guarded_statement)
            roots.extend(
                {"function": key, "source": source, "line": line} for key, line in visitor.calls if key in definitions
            )
    unique = {(root["function"], root["source"], root["line"]): root for root in roots}
    return [unique[key] for key in sorted(unique)]


def _operation_graph(operation: dict) -> dict:
    source_files = operation["source_files"]
    trees, modules_by_source = _collect_modules(source_files)
    known_modules = set(trees)
    definitions = {}
    for source, module in modules_by_source.items():
        visitor = _DefinitionVisitor(module, source)
        visitor.visit(trees[module])
        definitions.update(visitor.definitions)

    contexts = {}
    for source, module in modules_by_source.items():
        visitor = _ImportContextVisitor(module, source, known_modules, definitions)
        visitor.visit(trees[module])
        contexts[module] = visitor

    roots = _operation_roots(operation, modules_by_source, trees, contexts, definitions)
    queue = deque(root["function"] for root in roots)
    visited: set[str] = set()
    edges = set()
    while queue:
        key = queue.popleft()
        if key in visited or key not in definitions:
            continue
        visited.add(key)
        function = definitions[key]
        visitor = _CallVisitor(function, definitions, contexts)
        visitor.visit(function["node"])
        for edge in visitor.edges:
            edge_key = (edge["caller"], edge["callee"], edge["source"], edge["line"])
            edges.add(edge_key)
            if edge["callee"] not in visited:
                queue.append(edge["callee"])

    ordered_edges = [
        {"caller": caller, "callee": callee, "source": source, "line": line}
        for caller, callee, source, line in sorted(edges)
    ]
    ordered_functions = [
        {key: value for key, value in definitions[function].items() if key != "node"} for function in sorted(visited)
    ]
    return {
        "kind": operation["kind"],
        "name": operation["name"],
        "source_files": sorted(set(source_files)),
        "entry_functions": roots,
        "reachable_functions": ordered_functions,
        "direct_call_edges": ordered_edges,
    }


def build_inventory() -> dict:
    closure = worker_source_closure.build_inventory()
    operations = [_operation_graph(operation) for operation in closure["operations"]]
    source_files = {source for operation in closure["operations"] for source in operation["source_files"]}
    return {
        "version": 1,
        "generated_by": "scripts/worker_function_reachability.py",
        "scope": (
            "Direct statically resolved Python calls from allowlisted operation entry functions within their local services.* import closures. "
            "This graph is incomplete: dynamic dispatch, callbacks, methods on unknown instances, extension code, and database/provider behavior "
            "are not established. It is not an authorization policy or least-privilege grant list."
        ),
        "summary": {
            "operation_roots": len(operations),
            "source_files": len(source_files),
            "operations_without_resolved_entry_functions": sum(not item["entry_functions"] for item in operations),
            "function_memberships": sum(len(item["reachable_functions"]) for item in operations),
            "direct_call_edges": sum(len(item["direct_call_edges"]) for item in operations),
        },
        "operations": operations,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated graph")
    group.add_argument("--check", type=Path, help="Fail if the saved graph is stale")
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
        print(f"Missing worker function reachability graph: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Worker function reachability graph is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
