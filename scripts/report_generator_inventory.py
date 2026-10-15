#!/usr/bin/env python3
"""Build a source-only inventory of registered report generator inputs."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_SCOPE_PARAMETERS = {
    "location_id",
    "location_ids",
    "location",
    "organization_id",
    "organization_ids",
    "period_start",
    "period_end",
    "start_date",
    "end_date",
}


def _module_path(module: str) -> Path:
    relative = Path(*module.split("."))
    package_source = ROOT / relative / "__init__.py"
    if package_source.exists():
        return package_source
    return ROOT / relative.with_suffix(".py")


def _resolve_function(module: str, function_name: str, visited: frozenset[str] = frozenset()):
    if module in visited:
        return None
    source_path = _module_path(module)
    if not source_path.is_file():
        return None
    source_tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in source_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return source_path, node

    package_parts = module.split(".")
    next_visited = visited | {module}
    for node in source_tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            base_parts = package_parts[: len(package_parts) - (node.level - 1)]
            imported_module = ".".join([*base_parts, node.module]) if node.module else ".".join(base_parts)
        else:
            imported_module = node.module or ""
        for alias in node.names:
            if alias.name == "*" or (alias.asname or alias.name) == function_name:
                resolved = _resolve_function(
                    imported_module,
                    function_name if alias.name == "*" else alias.name,
                    next_visited,
                )
                if resolved is not None:
                    return resolved
    return None


def _function_signature(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[str], list[str]]:
    args = function.args
    positional = [*args.posonlyargs, *args.args]
    required_positional = positional[: len(positional) - len(args.defaults)] if args.defaults else positional
    required_keyword_only = [
        argument.arg
        for argument, default in zip(args.kwonlyargs, args.kw_defaults)
        if default is None
    ]
    parameters = [argument.arg for argument in positional]
    if args.vararg:
        parameters.append(args.vararg.arg)
    parameters.extend(argument.arg for argument in args.kwonlyargs)
    if args.kwarg:
        parameters.append(args.kwarg.arg)
    required = [argument.arg for argument in required_positional] + required_keyword_only
    return parameters, required


def build_inventory() -> dict:
    registry_path = ROOT / "services/export/reports/__init__.py"
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"), filename=str(registry_path))
    imported_functions = {}
    registry_assignment = None

    for node in registry_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            package_parts = ["services", "export", "reports"]
            module_parts = package_parts[: len(package_parts) - max(0, node.level - 1)]
            resolved_module = ".".join([*module_parts, node.module]) if node.level else node.module
            for alias in node.names:
                imported_functions[alias.asname or alias.name] = (resolved_module, alias.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "REPORT_GENERATORS" for target in targets):
                registry_assignment = node.value

    if not isinstance(registry_assignment, ast.Dict):
        raise RuntimeError("REPORT_GENERATORS must remain a literal source mapping")

    entries = []
    source_modules = set()
    with_location_input = 0
    with_period_inputs = 0

    for key_node, value_node in zip(registry_assignment.keys, registry_assignment.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            raise RuntimeError("Report type keys must be string literals")
        if not isinstance(value_node, ast.Name) or value_node.id not in imported_functions:
            raise RuntimeError(f"Report generator {key_node.value} must reference a directly imported callable")
        report_type = key_node.value
        module, function_name = imported_functions[value_node.id]
        resolved = _resolve_function(module, function_name)
        if resolved is None:
            raise RuntimeError(f"Report generator definition is missing for {report_type}: {function_name}")
        source_path, function = resolved
        parameter_names, required_parameters = _function_signature(function)
        scope_parameters = [name for name in parameter_names if name in _SCOPE_PARAMETERS]
        relative_source = source_path.relative_to(ROOT)
        defining_module_parts = list(relative_source.with_suffix("").parts)
        if defining_module_parts[-1] == "__init__":
            defining_module_parts.pop()
        defining_module = ".".join(defining_module_parts)
        source_modules.add(defining_module)
        with_location_input += "location_id" in parameter_names
        with_period_inputs += any(name in parameter_names for name in ("period_start", "period_end"))
        entries.append(
            {
                "report_type": report_type,
                "callable": function_name,
                "source_module": defining_module,
                "source_file": relative_source.as_posix(),
                "source_line": function.lineno,
                "parameters": parameter_names,
                "required_parameters": required_parameters,
                "scope_parameters": scope_parameters,
            }
        )

    entries.sort(key=lambda entry: entry["report_type"])

    return {
        "version": 1,
        "generated_by": "scripts/report_generator_inventory.py",
        "scope": (
            "Static inventory of the registered report callable, source location, and Python signature. "
            "Parameter names do not prove that SQL applies a tenant filter or that a report has semantic parity. "
            "No report is executed and no database, provider, or saved query is accessed."
        ),
        "summary": {
            "registered_report_types": len(entries),
            "source_modules": len(source_modules),
            "with_location_id_parameter": with_location_input,
            "with_period_start_or_end_parameter": with_period_inputs,
        },
        "reports": entries,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated report inventory")
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
        print(f"Missing report generator inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Report generator inventory is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
