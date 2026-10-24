"""Location-scoped, draft-only business canvas block edits."""

from __future__ import annotations

import json
from datetime import datetime
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context
from services.gateway.business_planning_writes import (
    _ARRAY_BLOCKS,
    _BLOCKS,
    BusinessPlanningWriteInvalid,
    _validate_json_value,
)


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


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
        raise BusinessPlanningWriteInvalid("Expected updated_at must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BusinessPlanningWriteInvalid("Expected updated_at must include a timezone")
    return parsed


def _normalize_edit_payload(block_name: str, payload: dict) -> tuple:
    fields = {
        "request_id",
        "expected_version",
        "expected_updated_at",
        "items",
        "change_reason",
    }
    if block_name not in _BLOCKS or not isinstance(payload, dict) or set(payload) != fields:
        raise BusinessPlanningWriteInvalid("Business canvas edit fields are invalid")

    request_id = _normalize_uuid(payload.get("request_id"), "request")
    expected_version = payload.get("expected_version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or not 1 <= expected_version < 2_147_483_647
    ):
        raise BusinessPlanningWriteInvalid("Expected version must be a positive integer")
    expected_updated_at = _expected_timestamp(payload.get("expected_updated_at"))

    items = payload.get("items")
    if block_name in _ARRAY_BLOCKS and not isinstance(items, list):
        raise BusinessPlanningWriteInvalid("Canvas list blocks must be arrays")
    if block_name == "cost_structure" and not isinstance(items, dict):
        raise BusinessPlanningWriteInvalid("Cost structure must be an object")
    _validate_json_value(items)
    try:
        encoded_items = json.dumps(
            items,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        encoded_items.encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise BusinessPlanningWriteInvalid("Canvas block must contain valid JSON values") from exc
    if len(encoded_items.encode("utf-8")) > 65_536:
        raise BusinessPlanningWriteInvalid("Canvas block must not exceed 65536 bytes")

    reason = payload.get("change_reason")
    if not isinstance(reason, str):
        raise BusinessPlanningWriteInvalid("A change reason is required")
    reason = reason.strip()
    if not 1 <= len(reason) <= 500 or "\x00" in reason:
        raise BusinessPlanningWriteInvalid("Change reason must contain 1 to 500 characters")
    return request_id, expected_version, expected_updated_at, encoded_items, reason


def update_location_business_model_canvas_block(
    operator_id: str,
    location_id: str,
    canvas_id: str,
    block_name: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Update one block on a draft canvas with request and version guards."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    canvas_id = _normalize_uuid(canvas_id, "canvas")
    request_id, expected_version, expected_updated_at, encoded_items, reason = (
        _normalize_edit_payload(block_name, payload)
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
                """SELECT * FROM kokonut_security.update_location_business_model_canvas_block(
                           %s::uuid, %s::uuid, %s::uuid, %s::integer,
                           %s::timestamptz, %s::text, %s::jsonb, %s::text
                       )""",
                (
                    location_id,
                    canvas_id,
                    request_id,
                    expected_version,
                    expected_updated_at,
                    block_name,
                    encoded_items,
                    reason,
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Business canvas edit returned no result")
        updated_canvas_id, status, version, updated_at, replayed = row
        connection.commit()
        return {
            "location_id": location_id,
            "canvas_id": str(updated_canvas_id),
            "block_name": block_name,
            "status": status,
            "version": version,
            "updated_at": updated_at,
            "replayed": bool(replayed),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
