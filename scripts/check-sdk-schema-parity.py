#!/usr/bin/env python3
"""Check selected Python/TypeScript SDK models against canonical SQL columns and types."""

from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_TABLES = {
    "Location": ("001_locations.sql", "location"),
    "Organization": ("064_organization.sql", "organization"),
    "OrganizationMember": ("064_organization.sql", "organization_member"),
    "Farm": ("001_locations.sql", "farm"),
    "Plot": ("001_locations.sql", "plot"),
    "CropCycle": ("002_crops.sql", "crop_cycle"),
    "HarvestEvent": ("003_operations.sql", "harvest_event"),
    "SalesEvent": ("003_operations.sql", "sales_event"),
    "ExpenseEvent": ("003_operations.sql", "expense_event"),
    "ExpenseCategory": ("004_finance.sql", "expense_category"),
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
JSONB_MODEL_SHAPES = {
    ("Location", "baseline_assumptions"): "json_object",
    ("Location", "metadata"): "json_object",
    ("Farm", "metadata"): "json_object",
    ("Farm", "data_privacy_criteria"): "json_object",
    ("Plot", "metadata"): "json_object",
    ("CropCycle", "metadata"): "json_object",
    ("HarvestEvent", "source_raw"): "json_object",
    ("SalesEvent", "source_raw"): "json_object",
    ("ExpenseEvent", "source_raw"): "json_object",
    ("NoiSnapshot", "inputs"): "json_object",
    ("LossEvent", "source_raw"): "json_object",
    ("LaborEvent", "source_raw"): "json_object",
    ("FieldNote", "source_raw"): "json_object",
    ("SensorReading", "metadata"): "json_object",
    ("SensorReading", "source_raw"): "json_object",
    ("SensorDevice", "metadata"): "json_object",
    ("AlertRule", "metadata"): "json_object",
    ("SensorAlert", "metadata"): "json_object",
    ("SensorAlert", "actuation_response"): "json_object",
    ("WalletProfile", "metadata"): "json_object",
    ("AttestationRecord", "claim_data"): "json_object",
    ("ReportSnapshot", "report_data"): "json_object",
    ("ReportSnapshot", "negative_findings"): "json_object_array",
    ("ExportLog", "filters"): "json_object",
    ("Organization", "metadata"): "json_object",
    ("OrganizationMember", "metadata"): "json_object",
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


def postgres_enum_types() -> dict[str, tuple[str, ...]]:
    enum_types: dict[str, tuple[str, ...]] = {}
    migrations = ROOT / "schemas" / "postgres"
    for migration in sorted(migrations.glob("*.sql")):
        source = re.sub(r"--[^\n]*", "", migration.read_text(encoding="utf-8"))
        for definition in re.finditer(
            r"CREATE TYPE\s+([a-z_][a-z0-9_]*)\s+AS\s+ENUM\s*\((.*?)\)",
            source,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            enum_types.setdefault(
                definition.group(1).lower(),
                tuple(re.findall(r"'((?:''|[^'])*)'", definition.group(2))),
            )
        for addition in re.finditer(
            r"ALTER TYPE\s+([a-z_][a-z0-9_]*)\s+ADD VALUE"
            r"(?:\s+IF NOT EXISTS)?\s+'((?:''|[^'])*)'",
            source,
            flags=re.IGNORECASE,
        ):
            type_name = addition.group(1).lower()
            if type_name in enum_types and addition.group(2) not in enum_types[type_name]:
                enum_types[type_name] += (addition.group(2),)
    return enum_types


def table_check_literals(path: Path, table: str) -> dict[str, tuple[str, ...]]:
    """Read simple column ``IN ('value', ...)`` checks from base SQL/migrations."""
    source = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
    table_match = re.search(
        rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}\s*\((.*?)\n\);",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if table_match is None:
        raise ValueError(f"canonical table {table!r} not found in {path.relative_to(ROOT)}")
    fragments = [table_match.group(1)]
    for migration_source in _postgres_migration_sources(ROOT):
        fragments.extend(
            statement.group(1)
            for statement in re.finditer(
                rf"ALTER TABLE\s+(?:ONLY\s+)?{re.escape(table)}\b(.*?);",
                migration_source,
                flags=re.IGNORECASE | re.DOTALL,
            )
        )
    values: dict[str, tuple[str, ...]] = {}
    for fragment in fragments:
        for check in re.finditer(
            r"\b([a-z_][a-z0-9_]*)\s+IN\s*\(([^()]*)\)",
            fragment,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            literals = tuple(
                value.replace("''", "'")
                for value in re.findall(r"'((?:''|[^'])*)'", check.group(2))
            )
            if literals:
                values[check.group(1).lower()] = literals
    return values


@lru_cache(maxsize=4)
def _postgres_migration_sources(root: Path) -> tuple[str, ...]:
    """Read ordered migration SQL once per source root for static inventories."""
    return tuple(
        re.sub(r"--[^\n]*", "", migration.read_text(encoding="utf-8"))
        for migration in sorted((root / "schemas" / "postgres").glob("*.sql"))
    )


def table_enum_columns(path: Path, table: str, enum_types: dict[str, tuple[str, ...]]) -> dict[str, str]:
    enum_columns = {
        column: sql_type.lower()
        for column, sql_type in table_column_types(path, table).items()
        if sql_type.lower() in enum_types
    }
    for migration in sorted((ROOT / "schemas" / "postgres").glob("*.sql")):
        source = re.sub(r"--[^\n]*", "", migration.read_text(encoding="utf-8"))
        statements = re.finditer(
            rf"ALTER TABLE\s+(?:ONLY\s+)?{re.escape(table)}\b(.*?);",
            source,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for statement in statements:
            for constraint in re.finditer(
                r"([a-z_][a-z0-9_]*)\s*::\s*([a-z_][a-z0-9_]*)\s+IS\s+NOT\s+NULL",
                statement.group(1),
                flags=re.IGNORECASE,
            ):
                column, type_name = constraint.group(1).lower(), constraint.group(2).lower()
                if type_name in enum_types:
                    enum_columns[column] = type_name
    return enum_columns


def sql_type_family(sql_type: str) -> str | None:
    normalized = sql_type.upper()
    if normalized == "JSONB":
        return "jsonb"
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


def python_type_matches_family(
    annotation: str,
    family: str,
    literal_aliases: dict[str, tuple[str, ...]] | None = None,
) -> bool:
    normalized = annotation.strip()
    if normalized.startswith("Optional[") and normalized.endswith("]"):
        normalized = normalized[len("Optional[") : -1].strip()
    normalized = re.sub(r"\s*\|\s*None\b", "", normalized).strip()
    if family == "string" and literal_aliases and normalized in literal_aliases:
        return all(isinstance(value, str) for value in literal_aliases[normalized])
    compatible = {
        "string": {"str"},
        "integer": {"int"},
        "number": {"float", "int", "Decimal"},
        "boolean": {"bool"},
        "string_array": {"List[str]", "list[str]"},
        "geojson_point": {"GeoJSONPoint"},
        "geojson_polygon": {"GeoJSONPolygon"},
        "json_object": {"JSONObject"},
        "json_object_array": {"List[JSONObject]", "list[JSONObject]"},
    }
    return normalized in compatible.get(family, set())


def typescript_type_matches_family(
    field_type: str,
    family: str,
    literal_aliases: dict[str, tuple[str, ...]] | None = None,
) -> bool:
    normalized = re.sub(r"\s*\|\s*null\b", "", field_type).strip()
    if family == "string":
        if literal_aliases and normalized in literal_aliases:
            return bool(literal_aliases[normalized])
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
        "json_object": "JSONObject",
        "json_object_array": "JSONObject[]",
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


def python_literal_aliases(path: Path) -> dict[str, tuple[str, ...]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if (
            not isinstance(target, ast.Name)
            or not isinstance(value, ast.Subscript)
            or not isinstance(value.value, ast.Name)
            or value.value.id != "Literal"
        ):
            continue
        literal_nodes = value.slice.elts if isinstance(value.slice, ast.Tuple) else [value.slice]
        literals = [
            item.value for item in literal_nodes
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]
        if len(literals) == len(literal_nodes):
            aliases[target.id] = tuple(literals)
    return aliases


def typescript_literal_aliases(path: Path) -> dict[str, tuple[str, ...]]:
    source = path.read_text(encoding="utf-8")
    aliases = {}
    for declaration in re.finditer(
        r"export type\s+(\w+)\s*=\s*([^;\n]+);", source
    ):
        parts = [part.strip() for part in declaration.group(2).split("|")]
        if parts and all(re.fullmatch(r"(?:'[^']*'|\"[^\"]*\")", part) for part in parts):
            aliases[declaration.group(1)] = tuple(
                part[1:-1] for part in parts
            )
    return aliases


def python_type_matches_enum(
    annotation: str, aliases: dict[str, tuple[str, ...]], expected: tuple[str, ...]
) -> bool:
    normalized = annotation.strip()
    if normalized.startswith("Optional[") and normalized.endswith("]"):
        normalized = normalized[len("Optional[") : -1].strip()
    normalized = re.sub(r"\s*\|\s*None\b", "", normalized).strip()
    return normalized in aliases and set(aliases[normalized]) == set(expected)


def typescript_type_matches_enum(
    field_type: str, aliases: dict[str, tuple[str, ...]], expected: tuple[str, ...]
) -> bool:
    normalized = re.sub(r"\s*\|\s*null\b", "", field_type).strip()
    return normalized in aliases and set(aliases[normalized]) == set(expected)


def python_type_matches_literals(
    annotation: str, aliases: dict[str, tuple[str, ...]], expected: tuple[str, ...]
) -> bool:
    return python_type_matches_enum(annotation, aliases, expected)


def typescript_type_matches_literals(
    field_type: str, aliases: dict[str, tuple[str, ...]], expected: tuple[str, ...]
) -> bool:
    return typescript_type_matches_enum(field_type, aliases, expected)


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
    python_enums = python_literal_aliases(ROOT / "sdk" / "python" / "kokonut" / "types.py")
    typescript_enums = typescript_literal_aliases(
        ROOT / "sdk" / "javascript" / "src" / "types.ts"
    )
    sql_enums = postgres_enum_types()
    failures = []
    checked_columns = 0
    checked_scalar_types = 0
    checked_spatial_types = 0
    checked_json_shapes = 0
    checked_enum_fields = 0
    checked_check_literal_fields = 0

    for model, (schema_file, table) in MODEL_TABLES.items():
        columns = table_columns(schema_dir / schema_file, table)
        nullable_columns = table_nullable_columns(schema_dir / schema_file, table)
        column_types = table_column_types(schema_dir / schema_file, table)
        enum_columns = table_enum_columns(schema_dir / schema_file, table, sql_enums)
        checked_literals = table_check_literals(schema_dir / schema_file, table)
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
            if family == "jsonb":
                family = JSONB_MODEL_SHAPES.get((model, column))
                if family is None:
                    failures.append(f"No JSONB SDK shape contract registered for {model}.{column}")
                    continue
            python_type = python_field_types.get(model, {}).get(column)
            typescript_type = typescript_field_types.get(model, {}).get(column)
            if python_type is None or typescript_type is None:
                continue
            if family.startswith("geojson_"):
                checked_spatial_types += 1
            elif family.startswith("json_"):
                checked_json_shapes += 1
            else:
                checked_scalar_types += 1
            if not python_type_matches_family(python_type, family, python_enums):
                failures.append(
                    f"Python {model}.{column} does not match SQL {sql_type}: {python_type}"
                )
            if not typescript_type_matches_family(typescript_type, family, typescript_enums):
                failures.append(
                    f"TypeScript {model}.{column} does not match SQL {sql_type}: "
                    f"{typescript_type}"
                )
        for column, enum_type in enum_columns.items():
            expected_values = sql_enums[enum_type]
            python_type = python_field_types.get(model, {}).get(column)
            typescript_type = typescript_field_types.get(model, {}).get(column)
            if python_type is None or typescript_type is None:
                continue
            checked_enum_fields += 1
            if not python_type_matches_enum(python_type, python_enums, expected_values):
                failures.append(
                    f"Python {model}.{column} does not match SQL enum {enum_type}: {python_type}"
                )
            if not typescript_type_matches_enum(typescript_type, typescript_enums, expected_values):
                failures.append(
                    f"TypeScript {model}.{column} does not match SQL enum "
                    f"{enum_type}: {typescript_type}"
                )
        for column, expected_values in checked_literals.items():
            if sql_type_family(column_types.get(column, "")) != "string":
                continue
            python_type = python_field_types.get(model, {}).get(column)
            typescript_type = typescript_field_types.get(model, {}).get(column)
            if python_type is None or typescript_type is None:
                continue
            checked_check_literal_fields += 1
            if not python_type_matches_literals(python_type, python_enums, expected_values):
                failures.append(
                    f"Python {model}.{column} does not match SQL CHECK values: {python_type}"
                )
            if not typescript_type_matches_literals(typescript_type, typescript_enums, expected_values):
                failures.append(
                    f"TypeScript {model}.{column} does not match SQL CHECK values: {typescript_type}"
                )

    if failures:
        print("SDK schema parity failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        f"SDK schema parity passed ({len(MODEL_TABLES)} models, "
        f"{checked_columns} canonical columns, {checked_scalar_types} scalar types, "
        f"{checked_spatial_types} PostGIS types, and {checked_json_shapes} JSONB shapes "
        f"plus {checked_enum_fields} enum fields and {checked_check_literal_fields} "
        f"CHECK-literal fields checked per SDK)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
