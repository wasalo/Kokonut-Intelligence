"""LinkML schema validation and management."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("linkml.validator")


def register_schema(conn, name: str, version: str, yaml_text: str, description: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO linkml_schema (name, version, description, schema_yaml, status) "
            "VALUES (:name, :version, :desc, :yaml, 'active') "
            "ON CONFLICT (name) DO UPDATE SET "
            "version = EXCLUDED.version, description = EXCLUDED.description, "
            "schema_yaml = EXCLUDED.schema_yaml, updated_at = NOW() "
            "RETURNING id"
        ),
        {"name": name, "version": version, "desc": description, "yaml": yaml_text},
    ).mappings().first()
    logger.info("Registered LinkML schema %s v%s", name, version)
    return {"id": str(result["id"]), "name": name, "version": version}


def get_schema(conn, name: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM linkml_schema WHERE name = :name ORDER BY version DESC LIMIT 1"),
        {"name": name},
    ).mappings().first()
    return dict(result) if result else None


def list_schemas(conn) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT id, name, version, description, status FROM linkml_schema ORDER BY name, version DESC")
    )
    return [dict(r) for r in result.mappings()]


def validate_instance(conn, schema_name: str, instance_data: dict) -> dict:
    schema = get_schema(conn, schema_name)
    if not schema:
        return {"is_valid": False, "errors": [f"Schema not found: {schema_name}"]}

    errors = []
    required_fields = _extract_required_fields(schema.get("schema_yaml", ""))
    for field in required_fields:
        if field not in instance_data:
            errors.append(f"Missing required field: {field}")

    entity_type = instance_data.get("@type", "unknown")
    entity_id = instance_data.get("@id", "unknown")

    conn.execute(
        conn.text(
            "INSERT INTO linkml_schema_instance "
            "(schema_id, entity_type, entity_id, instance_data, validation_errors, is_valid) "
            "VALUES (:sid, :et, :eid, :id, :ve, :iv)"
        ),
        {
            "sid": schema["id"], "et": entity_type, "eid": entity_id,
            "id": json.dumps(instance_data),
            "ve": json.dumps(errors) if errors else None,
            "iv": len(errors) == 0,
        },
    )

    return {"is_valid": len(errors) == 0, "errors": errors, "schema": schema_name}


def _extract_required_fields(yaml_text: str) -> list[str]:
    fields = []
    for line in yaml_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- name:") and "required: true" in yaml_text:
            name = stripped.split(":", 1)[1].strip()
            fields.append(name)
    return fields
