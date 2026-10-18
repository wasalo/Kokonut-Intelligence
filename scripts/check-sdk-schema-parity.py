#!/usr/bin/env python3
"""Ensure selected Python/TypeScript SDK models expose every canonical SQL column."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_TABLES = {
    "Location": ("001_locations.sql", "location"),
    "Farm": ("001_locations.sql", "farm"),
    "Plot": ("001_locations.sql", "plot"),
    "CropCycle": ("002_crops.sql", "crop_cycle"),
    "HarvestEvent": ("003_operations.sql", "harvest_event"),
    "SalesEvent": ("003_operations.sql", "sales_event"),
    "ExpenseEvent": ("003_operations.sql", "expense_event"),
    "SensorReading": ("005_environmental.sql", "sensor_reading"),
    "SensorType": ("011_sensor_registry.sql", "sensor_type"),
    "SensorDevice": ("011_sensor_registry.sql", "sensor_device"),
    "AlertRule": ("011_sensor_registry.sql", "alert_rule"),
    "SensorAlert": ("011_sensor_registry.sql", "sensor_alert"),
}


def table_columns(path: Path, table: str) -> set[str]:
    source = path.read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}\s*\((.*?)\n\);",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"canonical table {table!r} not found in {path.relative_to(ROOT)}")

    columns = set()
    for line in match.group(1).splitlines():
        declaration = line.split("--", maxsplit=1)[0].strip().rstrip(",")
        if not declaration:
            continue
        name = declaration.split(maxsplit=1)[0].strip('"')
        if re.fullmatch(r"[a-z][a-z0-9_]*", name):
            columns.add(name)
    return columns


def python_model_fields(path: Path) -> dict[str, set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: {
            field.target.id
            for field in node.body
            if isinstance(field, ast.AnnAssign) and isinstance(field.target, ast.Name)
        }
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }


def typescript_model_fields(path: Path) -> dict[str, set[str]]:
    source = path.read_text(encoding="utf-8")
    interfaces = re.finditer(
        r"export interface\s+(\w+)\s*\{(.*?)\n\}", source, flags=re.DOTALL
    )
    return {
        match.group(1): set(
            re.findall(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\??\s*:", match.group(2), re.MULTILINE)
        )
        for match in interfaces
    }


def main() -> int:
    schema_dir = ROOT / "schemas" / "postgres"
    python_models = python_model_fields(ROOT / "sdk" / "python" / "kokonut" / "types.py")
    typescript_models = typescript_model_fields(
        ROOT / "sdk" / "javascript" / "src" / "types.ts"
    )
    failures = []
    checked_columns = 0

    for model, (schema_file, table) in MODEL_TABLES.items():
        columns = table_columns(schema_dir / schema_file, table)
        checked_columns += len(columns)
        for language, models in (("Python", python_models), ("TypeScript", typescript_models)):
            fields = models.get(model)
            if fields is None:
                failures.append(f"{language} model {model} is missing")
                continue
            missing = sorted(columns - fields)
            if missing:
                failures.append(f"{language} {model} is missing SQL columns: {', '.join(missing)}")

    if failures:
        print("SDK schema parity failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        f"SDK schema parity passed ({len(MODEL_TABLES)} models, "
        f"{checked_columns} canonical columns checked per SDK)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
