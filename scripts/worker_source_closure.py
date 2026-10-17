#!/usr/bin/env python3
"""Build a conservative local-import inventory for allowlisted workers.

This is a source navigation aid, not a runtime call graph, effect proof, ACL,
or tenant policy. It follows statically resolvable imports under ``services``
and records unresolved dynamic import sites for manual review.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.security.execution_allowlist import (  # noqa: E402
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
)


def _module_paths(module_name: str) -> list[Path]:
    """Return existing Python source files represented by a module name."""
    if not module_name.startswith("services"):
        return []
    base = ROOT.joinpath(*module_name.split("."))
    if base.with_suffix(".py").is_file():
        return [base.with_suffix(".py")]
    if not base.is_dir():
        return []
    paths = [base / "__init__.py"]
    if (base / "__main__.py").is_file():
        paths.append(base / "__main__.py")
    return [path for path in paths if path.is_file()]


def _module_for_path(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_import_from(current_module: str, current_path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package = current_module
    if current_path.name != "__init__.py":
        package = current_module.rpartition(".")[0]
    relative_name = "." * node.level + (node.module or "")
    try:
        return importlib.util.resolve_name(relative_name, package)
    except ImportError:
        return ""


def _expression_is_import_module(node: ast.Call) -> bool:
    function = node.func
    return (
        (isinstance(function, ast.Name) and function.id == "__import__")
        or (isinstance(function, ast.Name) and function.id == "import_module")
        or (isinstance(function, ast.Attribute) and function.attr == "import_module")
    )


def _constant_module_argument(node: ast.Call) -> str | None:
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return None
    value = node.args[0].value
    return value if isinstance(value, str) else None


def _scan_source(path: Path) -> tuple[list[tuple[int, str, str]], list[dict[str, int | str]]]:
    """Return local import edges and unresolved dynamic-import locations."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"Unable to parse worker source {path.relative_to(ROOT)}") from exc

    current_module = _module_for_path(path)
    imports: set[tuple[int, str, str]] = set()
    dynamic_sites: set[tuple[int, str]] = set()

    def add_target(target: str, lineno: int, kind: str) -> None:
        if target == "services" or target.startswith("services."):
            imports.add((lineno, target, kind))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add_target(alias.name, node.lineno, "import")
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from(current_module, path, node)
            if base:
                add_target(base, node.lineno, "from")
                for alias in node.names:
                    if alias.name != "*":
                        submodule = f"{base}.{alias.name}"
                        if _module_paths(submodule):
                            add_target(submodule, node.lineno, "from-submodule")
        elif isinstance(node, ast.Call) and _expression_is_import_module(node):
            target = _constant_module_argument(node)
            if target is None:
                dynamic_sites.add((node.lineno, "dynamic module expression"))
            else:
                add_target(target, node.lineno, "dynamic constant")

    return sorted(imports), [{"line": line, "kind": kind} for line, kind in sorted(dynamic_sites)]


def _operation(kind: str, name: str, root_modules: list[str]) -> dict:
    pending = deque(root_modules)
    visited_modules: set[str] = set()
    sources: set[str] = set()
    edges: set[tuple[str, int, str, str]] = set()
    dynamic_sites: set[tuple[str, int, str]] = set()
    unresolved_modules: set[str] = set()

    while pending:
        module = pending.popleft()
        if module in visited_modules:
            continue
        visited_modules.add(module)
        paths = _module_paths(module)
        if not paths:
            unresolved_modules.add(module)
            continue
        for path in paths:
            source = path.relative_to(ROOT).as_posix()
            sources.add(source)
            local_imports, dynamic = _scan_source(path)
            for site in dynamic:
                dynamic_sites.add((source, int(site["line"]), str(site["kind"])))
            for line, target, import_kind in local_imports:
                target_paths = _module_paths(target)
                if not target_paths:
                    unresolved_modules.add(target)
                    continue
                resolved_target = _module_for_path(target_paths[0])
                edges.add((source, line, resolved_target, import_kind))
                if resolved_target not in visited_modules:
                    pending.append(resolved_target)

    return {
        "kind": kind,
        "name": name,
        "root_modules": sorted(set(root_modules)),
        "modules": sorted(visited_modules - unresolved_modules),
        "source_files": sorted(sources),
        "local_import_edges": [
            {"source": source, "line": line, "target": target, "kind": import_kind}
            for source, line, target, import_kind in sorted(edges)
        ],
        "unresolved_local_modules": sorted(unresolved_modules),
        "dynamic_import_sites": [
            {"source": source, "line": line, "kind": site_kind} for source, line, site_kind in sorted(dynamic_sites)
        ],
    }


def build_inventory() -> dict:
    operations = []
    for module in sorted(ALLOWED_SCHEDULED_MODULES):
        operations.append(_operation("scheduled_module", module, [module]))
    for module, function in sorted(ALLOWED_EVENT_HANDLERS):
        operations.append(_operation("event_handler", f"{module}.{function}", [module]))

    return {
        "version": 1,
        "generated_by": "scripts/worker_source_closure.py",
        "scope": (
            "Conservative static local-import closure for allowlisted worker modules. "
            "It does not prove function reachability, runtime effects, authorization, "
            "tenant context, or safe database grants."
        ),
        "operations": operations,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=False) + "\n"


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
        print(f"Missing worker source closure inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Worker source closure inventory is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
