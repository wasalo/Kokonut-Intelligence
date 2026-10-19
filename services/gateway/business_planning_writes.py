"""Location-scoped creation of governed business model canvas drafts."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_ARRAY_BLOCKS = (
    "key_partners",
    "key_activities",
    "key_resources",
    "value_propositions",
    "customer_relationships",
    "channels",
    "customer_segments",
    "revenue_streams",
)
_BLOCKS = (*_ARRAY_BLOCKS, "cost_structure")
_PAYLOAD_FIELDS = {"request_id", "canvas_name", "description", "fiscal_year", "tags", "blocks"}


class BusinessPlanningWriteInvalid(ValueError):
    """A business canvas draft request has invalid identifiers or fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise BusinessPlanningWriteInvalid(f"Invalid {field} identifier") from exc


def _validate_json_value(value, depth: int = 0) -> None:
    if depth > 32:
        raise BusinessPlanningWriteInvalid("Canvas blocks are nested too deeply")
    if isinstance(value, str):
        if "\x00" in value:
            raise BusinessPlanningWriteInvalid("Canvas blocks cannot contain null characters")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise BusinessPlanningWriteInvalid("Canvas block object keys must be strings")
            _validate_json_value(key, depth + 1)
            _validate_json_value(child, depth + 1)
        return
    if isinstance(value, list):
        for child in value:
            _validate_json_value(child, depth + 1)
        return
    if value is None or isinstance(value, (bool, int, float)):
        return
    raise BusinessPlanningWriteInvalid("Canvas blocks must contain valid JSON values")


def _normalize_payload(payload: dict) -> tuple[str, str, str | None, int | None, list[str], str]:
    if not isinstance(payload, dict) or set(payload) - _PAYLOAD_FIELDS:
        raise BusinessPlanningWriteInvalid("Business canvas fields are invalid")

    request_id = _normalize_uuid(payload.get("request_id"), "request")
    canvas_name = payload.get("canvas_name", "Primary Canvas")
    if not isinstance(canvas_name, str):
        raise BusinessPlanningWriteInvalid("Canvas name must be a string")
    canvas_name = canvas_name.strip()
    if not 1 <= len(canvas_name) <= 255 or "\x00" in canvas_name:
        raise BusinessPlanningWriteInvalid("Canvas name must contain 1 to 255 characters")

    description = payload.get("description")
    if description is not None:
        if not isinstance(description, str) or len(description) > 5000 or "\x00" in description:
            raise BusinessPlanningWriteInvalid("Description must contain at most 5000 characters")
        description = description.strip() or None

    fiscal_year = payload.get("fiscal_year")
    if fiscal_year is not None:
        if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int) or not 1900 <= fiscal_year <= 2200:
            raise BusinessPlanningWriteInvalid("Fiscal year must be an integer between 1900 and 2200")

    tags = payload.get("tags", [])
    if not isinstance(tags, list) or len(tags) > 30:
        raise BusinessPlanningWriteInvalid("Tags must be a list containing at most 30 entries")
    normalized_tags = []
    for tag in tags:
        if not isinstance(tag, str):
            raise BusinessPlanningWriteInvalid("Each tag must be a string")
        normalized = tag.strip()
        if not 1 <= len(normalized) <= 80 or "\x00" in normalized:
            raise BusinessPlanningWriteInvalid("Each tag must contain 1 to 80 characters")
        if normalized in normalized_tags:
            raise BusinessPlanningWriteInvalid("Tags must be unique")
        normalized_tags.append(normalized)

    provided_blocks = payload.get("blocks", {})
    if not isinstance(provided_blocks, dict) or set(provided_blocks) - set(_BLOCKS):
        raise BusinessPlanningWriteInvalid("Canvas blocks contain unsupported fields")
    blocks = {block: ([] if block != "cost_structure" else {}) for block in _BLOCKS}
    blocks.update(provided_blocks)
    if any(not isinstance(blocks[name], list) for name in _ARRAY_BLOCKS):
        raise BusinessPlanningWriteInvalid("Canvas list blocks must be arrays")
    if not isinstance(blocks["cost_structure"], dict):
        raise BusinessPlanningWriteInvalid("Cost structure must be an object")
    _validate_json_value(blocks)
    try:
        encoded_blocks = json.dumps(blocks, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        encoded_blocks.encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise BusinessPlanningWriteInvalid("Canvas blocks must contain valid JSON values") from exc
    if len(encoded_blocks.encode("utf-8")) > 65536:
        raise BusinessPlanningWriteInvalid("Canvas blocks must not exceed 65536 bytes")

    return request_id, canvas_name, description, fiscal_year, normalized_tags, encoded_blocks


def _write_canvas_on_connection(
    connection,
    location_id: str,
    normalized_payload: tuple[str, str, str | None, int | None, list[str], str],
) -> dict:
    request_id, canvas_name, description, fiscal_year, tags, encoded_blocks = normalized_payload
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT * FROM kokonut_security.create_location_business_model_canvas(
                       %s::uuid, %s::uuid, %s::text, %s::text, %s::integer,
                       %s::text[], %s::jsonb
                   )""",
            (
                location_id,
                request_id,
                canvas_name,
                description,
                fiscal_year,
                tags,
                encoded_blocks,
            ),
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Business canvas creation returned no result")
    canvas_id, status, version, created_at, replayed = row
    return {
        "location_id": location_id,
        "canvas_id": str(canvas_id),
        "status": status,
        "version": version,
        "created_at": created_at,
        "replayed": bool(replayed),
    }


def _create_location_business_model_canvas(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    generated: bool,
    connection_factory: Callable | None = None,
    suggestion_factory: Callable | None = None,
) -> dict:
    """Create a caller-composed or suggested draft under one signed transaction."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if not isinstance(payload, dict):
        raise BusinessPlanningWriteInvalid("Business canvas fields are invalid")
    if generated:
        if "blocks" in payload:
            raise BusinessPlanningWriteInvalid("Generated canvas blocks cannot be supplied by the caller")
        payload = dict(payload)
        payload.setdefault("canvas_name", "Primary Canvas (auto)")
        payload.setdefault("tags", ["auto-generated"])
    # Validate caller-controlled fields before opening a connection. Generated
    # blocks are validated again after the scoped suggestion reads.
    metadata_payload = {**payload, "blocks": {}} if generated else payload
    normalized_metadata = _normalize_payload(metadata_payload)
    if generated:
        normalized_tags = normalized_metadata[4]
        if "auto-generated" not in normalized_tags:
            normalized_tags.append("auto-generated")
        if any(tag.startswith("suggested-from:") for tag in normalized_tags):
            raise BusinessPlanningWriteInvalid("Generated source tags are reserved")
        if len(normalized_tags) + 20 > 30:
            raise BusinessPlanningWriteInvalid(
                "Generated canvases allow at most 10 base tags, including auto-generated"
            )
        payload["tags"] = normalized_tags

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="business_planning",
            action="create",
        )
        sources = []
        if generated:
            if suggestion_factory is None:
                from services.analytics.business_model_canvas import suggest

                suggestion_factory = suggest
            suggestion = suggestion_factory(connection, location_id)
            if not isinstance(suggestion, dict) or not isinstance(suggestion.get("blocks"), dict):
                raise RuntimeError("Business canvas suggestion source returned invalid data")
            sources = suggestion.get("generated_from", [])
            if (
                not isinstance(sources, list)
                or len(sources) > 20
                or any(not isinstance(source, str) or not 1 <= len(source) <= 80 for source in sources)
            ):
                raise RuntimeError("Business canvas suggestion provenance is invalid")
            create_payload = {**payload, "blocks": suggestion["blocks"]}
            tags = list(create_payload.get("tags") or [])
            tags.extend(f"suggested-from:{source}" for source in sources)
            if len(tags) > 30:
                raise BusinessPlanningWriteInvalid("Generated source tags exceed the canvas tag limit")
            create_payload["tags"] = tags
            normalized_payload = _normalize_payload(create_payload)
        else:
            normalized_payload = _normalize_payload(payload)

        result = _write_canvas_on_connection(connection, location_id, normalized_payload)
        connection.commit()
        if generated:
            result["generated_from"] = sources
            result["populated_blocks"] = [
                name for name, value in suggestion["blocks"].items() if value
            ]
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def create_location_business_model_canvas(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay one caller-composed, location-owned draft."""
    return _create_location_business_model_canvas(
        operator_id,
        location_id,
        payload,
        generated=False,
        connection_factory=connection_factory,
    )


def create_location_business_model_canvas_from_data(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
    suggestion_factory: Callable | None = None,
) -> dict:
    """Generate location-bound suggestions and create one draft atomically."""
    return _create_location_business_model_canvas(
        operator_id,
        location_id,
        payload,
        generated=True,
        connection_factory=connection_factory,
        suggestion_factory=suggestion_factory,
    )
