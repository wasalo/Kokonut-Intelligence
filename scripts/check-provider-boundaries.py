#!/usr/bin/env python3
"""Reject optional vendor imports outside explicit transport/provider adapters."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDARIES = {
    "clickhouse_connect": ("services/core/adapters/clickhouse.py",),
    "paho": ("services/core/adapters/mqtt.py",),
    "prefect": ("services/core/adapters/prefect.py",),
    "redis": ("services/core/adapters/redis.py",),
    "grpc": ("services/core/adapters/grpc.py", "services/grpc/", "services/security/interceptor.py"),
    "grpc_health": ("services/core/adapters/grpc.py", "services/grpc/"),
    "grpc_reflection": ("services/grpc/",),
    "grpc_tools": ("services/grpc/",),
}


def imports(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module, node.lineno
        elif isinstance(node, ast.Call) and ast.unparse(node.func) in {"importlib.import_module", "__import__"}:
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                yield node.args[0].value, node.lineno


def main() -> int:
    failures = []
    count = 0
    for path in sorted((ROOT / "services").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (SyntaxError, UnicodeError) as error:
            failures.append(f"{relative}: cannot inspect source: {error}")
            continue
        for module, line in imports(tree):
            allowed = BOUNDARIES.get(module.split(".")[0])
            if allowed is None:
                continue
            count += 1
            if not any(relative.startswith(item) if item.endswith("/") else relative == item for item in allowed):
                failures.append(f"{relative}:{line}: {module} must be imported through its provider adapter")
    for failure in failures:
        print(failure)
    if failures:
        return 1
    print(f"Provider boundaries passed ({count} vendor import sites)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
