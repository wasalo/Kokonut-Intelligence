#!/usr/bin/env python3
"""Generate public v1 response types and route templates from the OpenAPI snapshot.

Refresh the OpenAPI snapshot first, then run:

    python3 -m scripts.generate_public_api_sdk
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "docs/refactor/native-public-api-v1.openapi.json"
PYTHON_OUTPUT = ROOT / "sdk/python/kokonut/generated_public_api.py"
TYPESCRIPT_OUTPUT = ROOT / "sdk/javascript/src/generated/public-api-v1.ts"


def _reference_name(reference: str) -> str:
    return reference.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")


def _schema_type(schema: dict[str, Any], language: str) -> str:
    if "$ref" in schema:
        name = _reference_name(schema["$ref"])
        if not name.startswith("Public"):
            return "Any" if language == "python" else "unknown"
        return f"Api{name}" if language == "python" else f"{name}V1"

    if "const" in schema:
        literal = schema["const"]
        if language == "python":
            return f"Literal[{literal!r}]"
        return json.dumps(literal)

    if "enum" in schema:
        values = schema["enum"]
        if language == "python":
            return "Literal[" + ", ".join(repr(value) for value in values) + "]"
        return " | ".join(json.dumps(value) for value in values)

    alternatives = schema.get("anyOf") or schema.get("oneOf")
    if alternatives:
        non_null = [item for item in alternatives if item.get("type") != "null"]
        has_null = len(non_null) != len(alternatives)
        members = list(dict.fromkeys(_schema_type(item, language) for item in non_null))
        if not members:
            return "Any" if language == "python" else "unknown"
        if len(members) == 1:
            core = members[0]
        elif language == "python":
            core = "Union[" + ", ".join(members) + "]"
        else:
            core = " | ".join(members)
        if has_null:
            return f"Optional[{core}]" if language == "python" else f"{core} | null"
        return core

    value_type = schema.get("type")
    if value_type == "array":
        item_type = _schema_type(schema.get("items", {}), language)
        return f"list[{item_type}]" if language == "python" else f"{item_type}[]"
    if value_type == "object":
        if schema.get("properties"):
            return "Any" if language == "python" else "Record<string, unknown>"
        additional = schema.get("additionalProperties")
        if additional is False:
            return "dict[str, Any]" if language == "python" else "Record<string, never>"
        additional_type = _schema_type(additional, language) if isinstance(additional, dict) else (
            "Any" if language == "python" else "unknown"
        )
        return f"dict[str, {additional_type}]" if language == "python" else f"Record<string, {additional_type}>"
    if value_type == "integer":
        return "int" if language == "python" else "number"
    if value_type == "number":
        return "float" if language == "python" else "number"
    if value_type == "boolean":
        return "bool" if language == "python" else "boolean"
    if value_type == "string":
        return "str" if language == "python" else "string"
    return "Any" if language == "python" else "unknown"


def _public_schemas(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    schemas = spec.get("components", {}).get("schemas", {})
    return {name: schema for name, schema in sorted(schemas.items()) if name.startswith("Public")}


def _operations(spec: dict[str, Any]) -> dict[str, str]:
    operations: dict[str, str] = {}
    for path, methods in sorted(spec.get("paths", {}).items()):
        prefix = "/api/v1"
        if not path.startswith(prefix + "/"):
            raise ValueError(f"Versioned public path is outside {prefix}: {path}")
        for method, operation in sorted(methods.items()):
            operation_id = operation.get("operationId")
            if not operation_id:
                raise ValueError(f"Missing operationId for {method.upper()} {path}")
            if operation_id in operations:
                raise ValueError(f"Duplicate operationId in public contract: {operation_id}")
            policy = operation.get("x-kokonut-policy", {})
            if not policy.get("public") or policy.get("action") != "read":
                raise ValueError(f"Refusing to generate non-public read operation {operation_id}")
            if method.lower() != "get":
                raise ValueError(f"Unsupported public SDK method: {method.upper()} {path}")
            operations[operation_id] = path[len(prefix):]
    return dict(sorted(operations.items()))


def _generate_typescript(spec: dict[str, Any]) -> str:
    schemas = _public_schemas(spec)
    lines = [
        "/** Generated from docs/refactor/native-public-api-v1.openapi.json. Do not edit. */",
        "",
    ]
    for name, schema in schemas.items():
        properties = schema.get("properties")
        if schema.get("type") != "object" or not isinstance(properties, dict):
            continue
        required = set(schema.get("required", []))
        lines.append(f"export interface {name}V1 {{")
        for property_name, property_schema in sorted(properties.items()):
            optional = "" if property_name in required else "?"
            lines.append(
                f"  {property_name}{optional}: {_schema_type(property_schema, 'typescript')};"
            )
        lines.extend(["}", ""])
    lines.extend([
        "export const publicApiPathsV1 = {",
    ])
    for operation_id, path in _operations(spec).items():
        lines.append(f"  {operation_id}: {json.dumps(path)},")
    lines.extend(["} as const;", ""])
    return "\n".join(lines)


def _generate_python(spec: dict[str, Any]) -> str:
    schemas = _public_schemas(spec)
    lines = [
        '"""Generated response payload types from the native public v1 OpenAPI snapshot."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any, Literal, Optional, TypedDict, Union",
        "",
    ]
    for name, schema in schemas.items():
        properties = schema.get("properties")
        if schema.get("type") != "object" or not isinstance(properties, dict):
            continue
        required = set(schema.get("required", []))
        if required != set(properties):
            raise ValueError(f"Python generated public models require all keys: {name}")
        lines.append(f"class Api{name}(TypedDict):")
        for property_name, property_schema in sorted(properties.items()):
            lines.append(f"    {property_name}: {_schema_type(property_schema, 'python')}")
        if not properties:
            lines.append("    pass")
        lines.extend(["", ""])
    lines.extend(["PUBLIC_API_PATHS_V1 = {"])
    for operation_id, path in _operations(spec).items():
        lines.append(f"    {operation_id!r}: {path!r},")
    lines.extend(["}", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated SDK type/path files differ from the OpenAPI snapshot.",
    )
    args = parser.parse_args()
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    outputs = {
        PYTHON_OUTPUT: _generate_python(spec),
        TYPESCRIPT_OUTPUT: _generate_typescript(spec),
    }
    if args.check:
        stale = [
            path
            for path, contents in outputs.items()
            if not path.exists() or path.read_text(encoding="utf-8") != contents
        ]
        if stale:
            raise SystemExit("generated SDK files are stale: " + ", ".join(str(path.relative_to(ROOT)) for path in stale))
        print("generated SDK types and paths match the OpenAPI snapshot")
        return

    for path, contents in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        print(f"generated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
