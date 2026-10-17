#!/usr/bin/env python3
"""Inventory statically reachable local helper queries for report generators."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from report_generator_inventory import ROOT, _module_path, _resolve_function
from report_generator_inventory import build_inventory as build_source_inventory
from report_generator_query_scope_inventory import _analyze_function

_MAX_HELPER_FUNCTIONS_PER_REPORT = 128
_MAX_HELPER_DEPTH = 12


@lru_cache(maxsize=None)
def _resolve_function_cached(module: str, name: str):
    return _resolve_function_alias(module, name)


class _FunctionBodyVisitor(ast.NodeVisitor):
    """Walk one function body without treating nested function bodies as calls."""

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []
        self.imports: list[ast.Import | ast.ImportFrom] = []

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _absolute_import_module(module: str, level: int, imported: str | None) -> str:
    if not level:
        return imported or ""
    package = module.split(".")[:-1]
    base = package[: max(0, len(package) - level + 1)]
    return ".".join([*base, imported] if imported else base)


def _resolve_function_alias(
    module: str,
    name: str,
    visited: frozenset[tuple[str, str]] = frozenset(),
):
    """Resolve simple module-level function aliases without importing modules."""
    key = (module, name)
    if key in visited:
        return None
    resolved = _resolve_function(module, name)
    if resolved is not None:
        return resolved
    source = _module_path(module)
    if not source.is_file():
        return None
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    next_visited = visited | {key}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ) and isinstance(node.value, ast.Name):
            return _resolve_function_alias(module, node.value.id, next_visited)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name and isinstance(node.value, ast.Name):
                return _resolve_function_alias(module, node.value.id, next_visited)
        if isinstance(node, ast.ImportFrom):
            imported_module = _absolute_import_module(module, node.level, node.module)
            for alias in node.names:
                if (alias.asname or alias.name) == name:
                    return _resolve_function_alias(
                        imported_module, alias.name, next_visited
                    )
    return None


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def _function_body(function: ast.FunctionDef | ast.AsyncFunctionDef) -> _FunctionBodyVisitor:
    visitor = _FunctionBodyVisitor()
    for statement in function.body:
        visitor.visit(statement)
    return visitor


def _import_bindings(
    module: str,
    module_tree: ast.Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, list[tuple[int, str, str | None]]]:
    """Map imported names to source modules/functions without importing code."""
    bindings: dict[str, list[tuple[int, str, str | None]]] = defaultdict(list)
    body = _function_body(function)
    imports = [node for node in module_tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    imports.extend(body.imports)

    for node in imports:
        if isinstance(node, ast.ImportFrom):
            base = _absolute_import_module(module, node.level, node.module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                if _resolve_function_cached(base, alias.name) is not None:
                    bindings[local_name].append((node.lineno, base, alias.name))
                else:
                    submodule = f"{base}.{alias.name}" if base else alias.name
                    if _module_path(submodule).exists():
                        bindings[local_name].append((node.lineno, submodule, None))
                    elif base.startswith("services."):
                        bindings[local_name].append((node.lineno, base, alias.name))
        else:
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                target_module = alias.name if alias.asname else alias.name.split(".")[0]
                if _module_path(target_module).exists():
                    bindings[local_name].append((node.lineno, target_module, None))

    return bindings


def _resolve_call_target(
    call: ast.Call,
    module: str,
    bindings: dict[str, list[tuple[int, str, str | None]]],
) -> tuple[str, str] | None:
    dotted = _dotted_name(call.func)
    if not dotted:
        return None
    parts = dotted.split(".")
    candidates = [item for item in bindings.get(parts[0], []) if item[0] <= call.lineno]
    if candidates:
        _, target_module, target_function = max(candidates, key=lambda item: item[0])
        suffix = parts[1:]
        if target_function is not None:
            if suffix:
                return None
            return target_module, target_function
        if len(suffix) >= 1:
            return ".".join([target_module, *suffix[:-1]]), suffix[-1]
        return None
    if "." not in dotted and _top_level_function_exists(module, dotted):
        return module, dotted

    return None


_MODULE_FUNCTIONS: dict[str, set[str]] = {}
_MODULE_CLASSES: dict[str, set[str]] = {}


def _top_level_function_names(module: str) -> set[str]:
    if module not in _MODULE_FUNCTIONS:
        source = _module_path(module)
        if not source.is_file():
            _MODULE_FUNCTIONS[module] = set()
        else:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            _MODULE_FUNCTIONS[module] = {
                node.name
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return _MODULE_FUNCTIONS[module]


def _top_level_function_exists(module: str, name: str) -> bool:
    return name in _top_level_function_names(module)


def _top_level_class_exists(module: str, name: str) -> bool:
    if module not in _MODULE_CLASSES:
        source = _module_path(module)
        if not source.is_file():
            _MODULE_CLASSES[module] = set()
        else:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            _MODULE_CLASSES[module] = {
                node.name for node in tree.body if isinstance(node, ast.ClassDef)
            }
    return name in _MODULE_CLASSES[module]


def _calls_in_function(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Call]:
    return _function_body(function).calls


def _trace_report(
    report: dict,
    source_path: Path,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    module_tree: ast.Module,
) -> dict:
    report_module = _module_name(source_path)
    pending: list[tuple[str, str, list[str], int]] = []
    unresolved: list[dict] = []
    edges: list[dict] = []
    query_sites: dict[tuple[str, int], dict] = {}
    visited: set[str] = set()
    max_depth = _MAX_HELPER_DEPTH

    def enqueue_calls(
        caller_module: str,
        caller_function: ast.FunctionDef | ast.AsyncFunctionDef,
        caller_tree: ast.Module,
        path: list[str],
        depth: int,
    ) -> None:
        bindings = _import_bindings(caller_module, caller_tree, caller_function)
        for call in _calls_in_function(caller_function):
            target = _resolve_call_target(call, caller_module, bindings)
            dotted = _dotted_name(call.func) or "<dynamic>"
            if target is None:
                # Retain only unresolved calls which look like a local Kokonut
                # module/function reference; ordinary DB methods/builtins are
                # outside this helper-source map.
                if dotted.split(".")[0] in bindings:
                    unresolved.append(
                        {
                            "caller": path[-1],
                            "call": dotted,
                            "line": call.lineno,
                            "reason": "imported_target_not_resolved_to_local_function",
                        }
                    )
                continue
            target_module, target_function = target
            if not target_module.startswith("services."):
                continue
            resolved = _resolve_function_cached(target_module, target_function)
            if resolved is None:
                if _top_level_class_exists(target_module, target_function):
                    continue
                unresolved.append(
                    {
                        "caller": path[-1],
                        "call": dotted,
                        "line": call.lineno,
                        "reason": "local_function_source_not_found",
                    }
                )
                continue
            target_path, target_node = resolved
            target_label = f"{target_path.relative_to(ROOT).as_posix()}:{target_node.name}"
            edge = {
                "caller": path[-1],
                "callee": target_label,
                "line": call.lineno,
                "depth": depth + 1,
            }
            edges.append(edge)
            pending.append((target_module, target_node.name, [*path, target_label], depth + 1))

    enqueue_calls(report_module, function, module_tree, [report["callable"]], 0)
    while pending:
        current_module, current_name, call_path, depth = pending.pop(0)
        if len(visited) >= _MAX_HELPER_FUNCTIONS_PER_REPORT:
            unresolved.append(
                {
                    "caller": call_path[-1],
                    "call": current_name,
                    "line": None,
                    "reason": "maximum_helper_function_count_reached",
                }
            )
            break
        if depth > max_depth:
            unresolved.append(
                {
                    "caller": call_path[-1],
                    "call": current_name,
                    "line": None,
                    "reason": "maximum_helper_depth_reached",
                }
            )
            continue
        resolved = _resolve_function_cached(current_module, current_name)
        if resolved is None:
            continue
        helper_path, helper = resolved
        key = f"{helper_path.relative_to(ROOT).as_posix()}:{helper.name}"
        if key in visited:
            continue
        visited.add(key)
        analysis = _analyze_function(helper)
        for query in analysis["queries"]:
            query_key = (helper_path.relative_to(ROOT).as_posix(), query["line"])
            record = {
                "source_file": query_key[0],
                "callable": helper.name,
                "line": query["line"],
                "relations": query["relations"],
                "sql_source": query["sql_source"],
                "bound_location_scope_signal": query["bound_location_scope_signal"],
                "location_scope_conditionally_added": query["location_scope_conditionally_added"],
            }
            existing = query_sites.get(query_key)
            if existing:
                existing["reachable_via"].append(call_path)
            else:
                record["reachable_via"] = [call_path]
                query_sites[query_key] = record
        helper_module = _module_name(helper_path)
        helper_tree = ast.parse(helper_path.read_text(encoding="utf-8"), filename=str(helper_path))
        enqueue_calls(helper_module, helper, helper_tree, call_path, depth)

    queries = sorted(query_sites.values(), key=lambda item: (item["source_file"], item["line"]))
    scoped = sum(item["bound_location_scope_signal"] for item in queries)
    if not queries:
        classification = "no_query_sites_in_resolved_local_helper_closure"
    elif scoped == len(queries):
        classification = "all_resolved_helper_queries_show_location_scope_signal"
    elif scoped:
        classification = "mixed_resolved_helper_query_scope_signals"
    else:
        classification = "no_location_scope_signal_in_resolved_helper_queries"

    return {
        "report_type": report["report_type"],
        "report_source_file": report["source_file"],
        "report_callable": report["callable"],
        "resolved_helper_functions": sorted(visited),
        "resolved_helper_call_edges": sorted(edges, key=lambda item: (item["depth"], item["line"], item["callee"])),
        "reachable_helper_query_sites": queries,
        "helper_query_site_count": len(queries),
        "helper_query_sites_with_location_scope_signal": scoped,
        "classification": classification,
        "unresolved_local_helper_calls": sorted(
            unresolved, key=lambda item: (item["caller"], item["line"] or -1, item["call"])
        ),
    }


def build_inventory() -> dict:
    source_inventory = build_source_inventory()
    reports = []
    helper_query_sites = 0
    helper_scope_sites = 0
    reports_with_helper_queries = 0
    unresolved_calls = 0
    for report in source_inventory["reports"]:
        source_path = ROOT / report["source_file"]
        module_tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        function = next(
            node
            for node in module_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == report["callable"]
        )
        trace = _trace_report(report, source_path, function, module_tree)
        helper_query_sites += trace["helper_query_site_count"]
        helper_scope_sites += trace["helper_query_sites_with_location_scope_signal"]
        reports_with_helper_queries += trace["helper_query_site_count"] > 0
        unresolved_calls += len(trace["unresolved_local_helper_calls"])
        reports.append(trace)

    return {
        "version": 1,
        "generated_by": "scripts/report_generator_helper_scope_inventory.py",
        "scope": (
            "AST-only report-to-helper source trace. It follows statically imported or same-module local functions "
            "that resolve to unique Python definitions under services/. It records direct execute/query sites in "
            "the bounded local call closure without retaining SQL text or values. A location-scope signal is not "
            "proof of correct tenant authorization. Unresolved imports, dynamic dispatch, indirect function values, "
            "external providers, runtime call selection, database views, and semantic report behavior are not "
            "proven. No service is imported or executed and no database, provider, or secret is accessed."
        ),
        "summary": {
            "registered_report_types": len(reports),
            "reports_with_resolved_helper_query_sites": reports_with_helper_queries,
            "reachable_helper_query_sites_per_report": helper_query_sites,
            "helper_query_sites_with_location_scope_signal": helper_scope_sites,
            "unresolved_local_helper_calls": unresolved_calls,
        },
        "reports": sorted(reports, key=lambda item: item["report_type"]),
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the helper query inventory")
    group.add_argument("--check", type=Path, help="Fail if a saved inventory is stale")
    args = parser.parse_args(argv)
    expected = _serialize(build_inventory())

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(expected, encoding="utf-8")
        return 0
    if args.check:
        if not args.check.is_file() or args.check.read_text(encoding="utf-8") != expected:
            print(f"Stale report helper query inventory: {args.check}", file=sys.stderr)
            return 1
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
