#!/usr/bin/env python3
"""Create a static Kernel baseline without importing services or reading secrets.

Only tracked source descriptions, import edges, and environment variable NAMES
are collected. This is an inventory, not proof of runtime capability parity.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path

VENDORS = {
    "clickhouse_connect": "clickhouse",
    "redis": "redis",
    "prefect": "prefect",
    "paho": "mqtt",
    "grpc": "grpc",
    "grpc_tools": "grpc",
    "grpc_health": "grpc",
    "grpc_reflection": "grpc",
}


def source_facts(path: Path, root: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports, environment, routes = [], set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((item.name, node.lineno) for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imports.append((node.module, node.lineno))
            imports.extend((f"{node.module}.{item.name}", node.lineno) for item in node.names)
        elif isinstance(node, ast.Call):
            function = ast.unparse(node.func)
            if function in {"os.getenv", "os.environ.get", "environ.get", "getenv"}:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    environment.add(node.args[0].value)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in {"get", "post", "put", "patch", "delete", "websocket"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"app", "router"}
            ):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    routes.append({"method": node.func.attr.upper(), "path": node.args[0].value, "line": node.lineno})
        elif isinstance(node, ast.Subscript) and ast.unparse(node.value) == "os.environ":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                environment.add(node.slice.value)
    return {
        "path": path.relative_to(root).as_posix(),
        "imports": sorted(set(imports)),
        "environment_names": sorted(environment),
        "routes": routes,
    }


def build_inventory(root: Path) -> dict:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    facts, errors = [], []
    for parent in ("services", "tests"):
        for path in sorted((root / parent).rglob("*.py")):
            try:
                facts.append(source_facts(path, root))
            except (SyntaxError, UnicodeError) as error:
                errors.append({"path": path.relative_to(root).as_posix(), "error": str(error)})
    groups = {}
    for fact in facts:
        parts = Path(fact["path"]).parts
        if parts[0] != "services" or len(parts) < 3:
            continue
        group = groups.setdefault(parts[1], {"modules": [], "environment_names": set(), "test_references": []})
        group["modules"].append(fact["path"])
        group["environment_names"].update(fact["environment_names"])
    for name, group in groups.items():
        prefix = f"services.{name}"
        group["environment_names"] = sorted(group["environment_names"])
        group["test_references"] = sorted(
            {
                fact["path"]
                for fact in facts
                if fact["path"].startswith("tests/")
                and any(module == prefix or module.startswith(prefix + ".") for module, _ in fact["imports"])
            }
        )
    vendor_edges = []
    for fact in facts:
        if not fact["path"].startswith("services/"):
            continue
        for module, line in fact["imports"]:
            if module.split(".")[0] in VENDORS:
                vendor_edges.append(
                    {"provider": VENDORS[module.split(".")[0]], "path": fact["path"], "module": module, "line": line}
                )
    capabilities, category, in_capabilities = [], "", False
    for line in (root / "README.md").read_text().splitlines():
        if line.startswith("## Core Capabilities"):
            in_capabilities = True
        elif in_capabilities and line.startswith("## "):
            break
        elif in_capabilities and line.startswith("|"):
            cells = [cell.strip().replace("**", "") for cell in line.strip("|").split("|")]
            if len(cells) != 3 or cells[0] == "Category" or all(set(cell) <= {"-", ":", " "} for cell in cells):
                continue
            category = cells[0] or category
            capabilities.append(
                {
                    "id": f"CAP-{len(capabilities) + 1:03}",
                    "category": category,
                    "name": cells[1],
                    "description": cells[2],
                    "parity": "not_yet_validated",
                }
            )
    ownership = (root / "docs/data-model/domain-ownership.md").read_text()
    domains = []
    for section in re.split(r"(?m)^### ", ownership)[1:]:
        name = section.splitlines()[0]
        references = re.findall(r"`([^`]+)`", section.split("## Ownership Rules")[0])
        domains.append(
            {
                "name": name,
                "services": sorted({ref for ref in references if ref.startswith("services/")}),
                "migrations": sorted({ref for ref in references if ref.endswith(".sql")}),
            }
        )
    schemas = {}
    for kind in ("postgres", "clickhouse", "seeds"):
        schemas[kind] = [path.relative_to(root).as_posix() for path in sorted((root / "schemas" / kind).glob("*.sql"))]
    return {
        "format_version": 1,
        "baseline_commit": sha,
        "limitations": [
            "Static references are coverage candidates, not test results.",
            "No runtime environment values or business records are collected.",
            "Dynamic imports, SQL data lineage, and route policies require manual review.",
        ],
        "capabilities": capabilities,
        "domains": domains,
        "service_groups": groups,
        "vendor_import_edges": vendor_edges,
        "schemas": schemas,
        "http_routes": [
            {"source": fact["path"], **route}
            for fact in facts
            for route in fact["routes"]
            if fact["path"].startswith("services/")
        ],
        "test_files": [
            fact["path"]
            for fact in facts
            if Path(fact["path"]).name.startswith("test_") and fact["path"].startswith("tests/")
        ],
        "parse_errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write JSON to this path; default is stdout")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    inventory = build_inventory(root)
    rendered = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(
            f"Inventory: {len(inventory['capabilities'])} capabilities, "
            f"{len(inventory['service_groups'])} service groups, "
            f"{len(inventory['test_files'])} test files, "
            f"{len(inventory['parse_errors'])} parse errors"
        )
    else:
        print(rendered, end="")
    if inventory["parse_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
