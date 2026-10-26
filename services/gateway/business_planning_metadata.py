"""Location-scoped, draft-only business canvas metadata edits."""

from __future__ import annotations

import json
from datetime import datetime
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context
from services.gateway.business_planning_writes import (
    BusinessPlanningWriteInvalid,
    _validate_json_value,
)

_EDIT_FIELDS = frozenset({"canvas_name", "description", "fiscal_year", "tags"})
_ENVELOPE_FIELDS = frozenset(
    {"request_id", "expected_version", "expected_updated_at", "change_reason"}
)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise BusinessPlanningWriteInvalid(f"Invalid {field} identifier") from exc


def _expected_timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise BusinessPlanningWriteInvalid("Expected updated_at is required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise BusinessPlanningWriteInvalid(
            "Expected updated_at must be an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BusinessPlanningWriteInvalid("Expected updated_at must include a timezone")
    return parsed


def _normalize_metadata_payload(payload: dict) -> tuple[str, int, datetime, str, str, str]:
    if not isinstance(payload, dict):
        raise BusinessPlanningWriteInvalid("Business canvas metadata must be a JSON object")
    supplied = set(payload)
    if not _ENVELOPE_FIELDS <= supplied or supplied - _ENVELOPE_FIELDS - _EDIT_FIELDS:
        raise BusinessPlanningWriteInvalid("Business canvas metadata edit fields are invalid")
    fields = supplied - _ENVELOPE_FIELDS
    if not fields:
        raise BusinessPlanningWriteInvalid("At least one canvas metadata field is required")

    request_id = _normalize_uuid(payload.get("request_id"), "request")
    expected_version = payload.get("expected_version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or not 1 <= expected_version < 2_147_483_647
    ):
        raise BusinessPlanningWriteInvalid("Expected version must be a positive integer")
    expected_updated_at = _expected_timestamp(payload.get("expected_updated_at"))
    reason = payload.get("change_reason")
    if not isinstance(reason, str):
        raise BusinessPlanningWriteInvalid("A change reason is required")
    reason = reason.strip()
    if not 1 <= len(reason) <= 500 or "\x00" in reason:
        raise BusinessPlanningWriteInvalid("Change reason must contain 1 to 500 characters")

    normalized: dict[str, object] = {}
    if "canvas_name" in fields:
        name = payload["canvas_name"]
        if not isinstance(name, str):
            raise BusinessPlanningWriteInvalid("Canvas name must be a string")
        name = name.strip()
        if not 1 <= len(name) <= 255 or "\x00" in name:
            raise BusinessPlanningWriteInvalid("Canvas name must contain 1 to 255 characters")
        normalized["canvas_name"] = name
    if "description" in fields:
        description = payload["description"]
        if description is not None and not isinstance(description, str):
            raise BusinessPlanningWriteInvalid("Canvas description must be a string or null")
        if description is not None:
            description = description.strip()
            if len(description) > 4000 or "\x00" in description:
                raise BusinessPlanningWriteInvalid(
                    "Canvas description must be at most 4000 characters"
                )
        normalized["description"] = description
    if "fiscal_year" in fields:
        fiscal_year = payload["fiscal_year"]
        if fiscal_year is not None and (
            isinstance(fiscal_year, bool)
            or not isinstance(fiscal_year, int)
            or not 1900 <= fiscal_year <= 2200
        ):
            raise BusinessPlanningWriteInvalid(
                "Fiscal year must be null or an integer from 1900 through 2200"
            )
        normalized["fiscal_year"] = fiscal_year
    if "tags" in fields:
        tags = payload["tags"]
        if not isinstance(tags, list) or len(tags) > 50:
            raise BusinessPlanningWriteInvalid("Canvas tags must be an array of at most 50 strings")
        normalized_tags: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            if not isinstance(tag, str):
                raise BusinessPlanningWriteInvalid("Canvas tags must contain strings only")
            normalized_tag = tag.strip()
            folded = normalized_tag.casefold()
            if not 1 <= len(normalized_tag) <= 64 or "\x00" in normalized_tag:
                raise BusinessPlanningWriteInvalid(
                    "Canvas tags must contain 1 to 64 non-empty characters"
                )
            if folded in seen:
                raise BusinessPlanningWriteInvalid("Canvas tags must not contain duplicates")
            seen.add(folded)
            normalized_tags.append(normalized_tag)
        normalized["tags"] = normalized_tags

    _validate_json_value(normalized)
    try:
        encoded_fields = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        encoded_fields.encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise BusinessPlanningWriteInvalid("Canvas metadata must contain valid JSON values") from exc
    if len(encoded_fields.encode("utf-8")) > 16_384:
        raise BusinessPlanningWriteInvalid("Canvas metadata edit must not exceed 16384 bytes")
    return (
        request_id,
        expected_version,
        expected_updated_at,
        encoded_fields,
        reason,
        ",".join(sorted(fields)),
    )


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def update_location_business_model_canvas_metadata(
    operator_id: str,
    location_id: str,
    canvas_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Update allowlisted metadata on one draft canvas with version guards."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    canvas_id = _normalize_uuid(canvas_id, "canvas")
    request_id, expected_version, expected_updated_at, encoded_fields, reason, changed_fields = (
        _normalize_metadata_payload(payload)
    )

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
            action="update",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.update_location_business_model_canvas_metadata(
                           %s::uuid, %s::uuid, %s::uuid, %s::integer,
                           %s::timestamptz, %s::jsonb, %s::text
                       )""",
                (
                    location_id,
                    canvas_id,
                    request_id,
                    expected_version,
                    expected_updated_at,
                    encoded_fields,
                    reason,
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Business canvas metadata edit returned no result")
        updated_canvas_id, status, version, updated_at, replayed = row
        connection.commit()
        return {
            "location_id": location_id,
            "canvas_id": str(updated_canvas_id),
            "status": status,
            "version": version,
            "updated_at": updated_at,
            "replayed": bool(replayed),
            "changed_fields": changed_fields.split(","),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
