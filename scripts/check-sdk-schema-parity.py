#!/usr/bin/env python3
"""Check selected Python/TypeScript SDK models against canonical SQL columns and types."""

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
    "NoiSnapshot": ("004_finance.sql", "noi_snapshot"),
    "LossEvent": ("003_operations.sql", "loss_event"),
    "LaborEvent": ("003_operations.sql", "labor_event"),
    "FieldNote": ("003_operations.sql", "field_note"),
    "SensorReading": ("005_environmental.sql", "sensor_reading"),
    "SensorType": ("011_sensor_registry.sql", "sensor_type"),
    "SensorDevice": ("011_sensor_registry.sql", "sensor_device"),
    "AlertRule": ("011_sensor_registry.sql", "alert_rule"),
    "SensorAlert": ("011_sensor_registry.sql", "sensor_alert"),
    "WalletProfile": ("006_web3.sql", "wallet_profile"),
    "AttestationRecord": ("006_web3.sql", "attestation_record"),
    "ReportSnapshot": ("007_modeled_outputs.sql", "report_snapshot"),
    "ExportLog": ("008_governance.sql", "export_log"),
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
    # Include additive column migrations so the guard follows the evolved
    # schema, not just the initial CREATE TABLE declaration.
    for migration in (ROOT / "schemas" / "postgres").glob("*.sql"):
        migration_source = re.sub(r"--[^\n]*", "", migration.read_text(encoding="utf-8"))
        statements = re.finditer(
            rf"ALTER TABLE\s+(?:ONLY\s+)?{re.escape(table)}\b(.*?);",
            migration_source,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for statement in statements:
            columns.update(
                name.lower()
                for name in re.findall(
                    r"ADD COLUMN(?:\s+IF NOT EXISTS)?\s+([a-z_][a-z0-9_]*)",
                    statement.group(1),
                    flags=re.IGNORECASE,
                )
            )
    return columns


def table_nullable_columns(path: Path, table: str) -> set[str]:
    source = path.read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}\s*\((.*?)\n\);",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"canonical table {table!r} not found in {path.relative_to(ROOT)}")

    nullability = {}
    for line in match.group(1).splitlines():
        declaration = line.split("--", maxsplit=1)[0].strip().rstrip(",")
        if not declaration:
            continue
        name = declaration.split(maxsplit=1)[0].strip('"').lower()
        if name in {"constraint", "primary", "unique", "check", "foreign"}:
            continue
        if re.fullmatch(r"[a-z][a-z0-9_]*", name):
            nullability[name] = not bool(
                re.search(r"\b(?:NOT\s+NULL|PRIMARY\s+KEY)\b", declaration, re.IGNORECASE)
            )

    for migration in sorted((ROOT / "schemas" / "postgres").glob("*.sql")):
        migration_source = re.sub(r"--[^\n]*", "", migration.read_text(encoding="utf-8"))
        statements = re.finditer(
            rf"ALTER TABLE\s+(?:ONLY\s+)?{re.escape(table)}\b(.*?);",
            migration_source,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for statement in statements:
            body = statement.group(1)
            additions = list(
                re.finditer(
                    r"ADD COLUMN(?:\s+IF NOT EXISTS)?\s+([a-z_][a-z0-9_]*)",
                    body,
                    flags=re.IGNORECASE,
                )
            )
            for index, addition in enumerate(additions):
                end = additions[index + 1].start() if index + 1 < len(additions) else len(body)
                definition = body[addition.end() : end]
                nullability[addition.group(1).lower()] = not bool(
                    re.search(r"\b(?:NOT\s+NULL|PRIMARY\s+KEY)\b", definition, re.IGNORECASE)
                )

            for alteration in re.finditer(
                r"ALTER COLUMN\s+([a-z_][a-z0-9_]*)\s+(SET|DROP)\s+NOT\s+NULL",
                body,
                flags=re.IGNORECASE,
            ):
                nullability[alteration.group(1).lower()] = (
                    alteration.group(2).upper() == "DROP"
                )

    return {name for name, nullable in nullability.items() if nullable}


def parse_sql_type(declaration: str) -> str | None:
    match = re.match(
        r"\s*((?:DOUBLE\s+PRECISION|TIMESTAMP\s+WITH(?:OUT)?\s+TIME\s+ZONE|"
        r"CHARACTER\s+VARYING|[A-Z][A-Z0-9_]*)(?:\s*\([^)]*\))?(?:\[\])?)",
        declaration,
        flags=re.IGNORECASE,
    )
    return match.group(1).upper() if match else None


def table_column_types(path: Path, table: str) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}\s*\((.*?)\n\);",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"canonical table {table!r} not found in {path.relative_to(ROOT)}")

    column_types = {}
    for line in match.group(1).splitlines():
        declaration = line.split("--", maxsplit=1)[0].strip().rstrip(",")
        column = re.match(r"([a-z][a-z0-9_]*)\s+(.+)", declaration, re.IGNORECASE)
        if column is None or column.group(1).lower() in {
            "constraint",
            "primary",
            "unique",
            "check",
            "foreign",
        }:
            continue
        sql_type = parse_sql_type(column.group(2))
        if sql_type:
            column_types[column.group(1).lower()] = sql_type

    for migration in sorted((ROOT / "schemas" / "postgres").glob("*.sql")):
        migration_source = re.sub(r"--[^\n]*", "", migration.read_text(encoding="utf-8"))
        statements = re.finditer(
            rf"ALTER TABLE\s+(?:ONLY\s+)?{re.escape(table)}\b(.*?);",
            migration_source,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for statement in statements:
            body = statement.group(1)
            additions = list(
                re.finditer(
                    r"ADD COLUMN(?:\s+IF NOT EXISTS)?\s+([a-z_][a-z0-9_]*)",
                    body,
                    flags=re.IGNORECASE,
                )
            )
            for index, addition in enumerate(additions):
                end = additions[index + 1].start() if index + 1 < len(additions) else len(body)
                sql_type = parse_sql_type(body[addition.end() : end])
                if sql_type:
                    column_types[addition.group(1).lower()] = sql_type

            for alteration in re.finditer(
                r"ALTER COLUMN\s+([a-z_][a-z0-9_]*)\s+TYPE\s+(.+?)(?=,\s*ALTER COLUMN|$)",
                body,
                flags=re.IGNORECASE,
            ):
                sql_type = parse_sql_type(alteration.group(2))
                if sql_type:
                    column_types[alteration.group(1).lower()] = sql_type

    return column_types


def sql_type_family(sql_type: str) -> str | None:
    normalized = sql_type.upper()
    if normalized == "UUID" or normalized in {
        "TEXT",
        "DATE",
        "TIME",
        "TIMESTAMP",
        "TIMESTAMPTZ",
        "TIMESTAMP WITH TIME ZONE",
        "TIMESTAMP WITHOUT TIME ZONE",
    } or normalized.startswith(("VARCHAR", "CHARACTER VARYING", "CHAR(")):
        return "string"
    if normalized in {"SMALLINT", "INTEGER", "INT", "BIGINT", "SERIAL", "BIGSERIAL"}:
        return "integer"
    if normalized.startswith(("NUMERIC", "DECIMAL", "REAL", "DOUBLE PRECISION", "FLOAT")):
        return "number"
    if normalized in {"BOOLEAN", "BOOL"}:
        return "boolean"
    if normalized in {"TEXT[]", "VARCHAR[]"}:
        return "string_array"
    spatial_type = re.fullmatch(
        r"(?:GEOMETRY|GEOGRAPHY)\s*\(\s*(POINT|POLYGON)\s*,\s*\d+\s*\)",
        normalized,
    )
    if spatial_type:
        return f"geojson_{spatial_type.group(1).lower()}"
    return None


def python_type_matches_family(annotation: str, family: str) -> bool:
    normalized = annotation.strip()
    if normalized.startswith("Optional[") and normalized.endswith("]"):
        normalized = normalized[len("Optional[") : -1].strip()
    normalized = re.sub(r"\s*\|\s*None\b", "", normalized).strip()
    compatible = {
        "string": {"str"},
        "integer": {"int"},
        "number": {"float", "int", "Decimal"},
        "boolean": {"bool"},
        "string_array": {"List[str]", "list[str]"},
        "geojson_point": {"GeoJSONPoint"},
        "geojson_polygon": {"GeoJSONPolygon"},
    }
    return normalized in compatible.get(family, set())


def typescript_type_matches_family(field_type: str, family: str) -> bool:
    normalized = re.sub(r"\s*\|\s*null\b", "", field_type).strip()
    if family == "string":
        parts = [part.strip() for part in normalized.split("|")]
        return bool(parts) and all(
            part == "string" or re.fullmatch(r"(?:'[^']*'|\"[^\"]*\")", part)
            for part in parts
        )
    expected = {
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "string_array": "string[]",
        "geojson_point": "GeoJSONPoint",
        "geojson_polygon": "GeoJSONPolygon",
    }.get(family)
    return normalized == expected


def python_model_field_types(path: Path) -> dict[str, dict[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: {
            field.target.id: ast.unparse(field.annotation)
            for field in node.body
            if isinstance(field, ast.AnnAssign)
            and isinstance(field.target, ast.Name)
            and field.annotation is not None
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


def typescript_model_field_types(path: Path) -> dict[str, dict[str, str]]:
    source = path.read_text(encoding="utf-8")
    interfaces = re.finditer(
        r"export interface\s+(\w+)\s*\{(.*?)\n\}", source, flags=re.DOTALL
    )
    return {
        match.group(1): {
            name: field_type.strip()
            for name, field_type in re.findall(
                r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\??\s*:\s*([^;\n]+)",
                match.group(2),
                flags=re.MULTILINE,
            )
        }
        for match in interfaces
    }


def main() -> int:
    schema_dir = ROOT / "schemas" / "postgres"
    python_field_types = python_model_field_types(
        ROOT / "sdk" / "python" / "kokonut" / "types.py"
    )
    python_models = {model: set(fields) for model, fields in python_field_types.items()}
    typescript_models = typescript_model_fields(
        ROOT / "sdk" / "javascript" / "src" / "types.ts"
    )
    typescript_field_types = typescript_model_field_types(
        ROOT / "sdk" / "javascript" / "src" / "types.ts"
    )
    failures = []
    checked_columns = 0
    checked_scalar_types = 0
    checked_spatial_types = 0

    for model, (schema_file, table) in MODEL_TABLES.items():
        columns = table_columns(schema_dir / schema_file, table)
        nullable_columns = table_nullable_columns(schema_dir / schema_file, table)
        column_types = table_column_types(schema_dir / schema_file, table)
        checked_columns += len(columns)
        for language, models in (("Python", python_models), ("TypeScript", typescript_models)):
            fields = models.get(model)
            if fields is None:
                failures.append(f"{language} model {model} is missing")
                continue
            missing = sorted(columns - fields)
            if missing:
                failures.append(f"{language} {model} is missing SQL columns: {', '.join(missing)}")
        nullable_without_null = sorted(
            column
            for column in nullable_columns
            if column in typescript_field_types.get(model, {})
            and not re.search(r"\bnull\b", typescript_field_types[model][column])
        )
        if nullable_without_null:
            failures.append(
                f"TypeScript {model} omits null from nullable SQL columns: "
                f"{', '.join(nullable_without_null)}"
            )
        nullable_without_optional = sorted(
            column
            for column in nullable_columns
            if column in python_field_types.get(model, {})
            and not re.search(
                r"\b(?:Optional|None)\b", python_field_types[model][column]
            )
        )
        if nullable_without_optional:
            failures.append(
                f"Python {model} omits Optional from nullable SQL columns: "
                f"{', '.join(nullable_without_optional)}"
            )
        for column, sql_type in column_types.items():
            family = sql_type_family(sql_type)
            if family is None:
                continue
            python_type = python_field_types.get(model, {}).get(column)
            typescript_type = typescript_field_types.get(model, {}).get(column)
            if python_type is None or typescript_type is None:
                continue
            if family.startswith("geojson_"):
                checked_spatial_types += 1
            else:
                checked_scalar_types += 1
            if not python_type_matches_family(python_type, family):
                failures.append(
                    f"Python {model}.{column} does not match SQL {sql_type}: {python_type}"
                )
            if not typescript_type_matches_family(typescript_type, family):
                failures.append(
                    f"TypeScript {model}.{column} does not match SQL {sql_type}: "
                    f"{typescript_type}"
                )

    if failures:
        print("SDK schema parity failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        f"SDK schema parity passed ({len(MODEL_TABLES)} models, "
        f"{checked_columns} canonical columns, {checked_scalar_types} scalar types, and "
        f"{checked_spatial_types} PostGIS types checked per SDK)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
