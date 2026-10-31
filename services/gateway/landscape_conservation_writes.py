"""Location-scoped landscape capture through bounded database functions.

The SQL function is added in the final migration phase. This module deliberately
does not issue direct table DML: the database contract will own authorization,
location binding (including habitat references), idempotency, and capture audit.
"""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_INITIAL_STATUS = {
    "habitat_zone": "active",
    "wildlife_corridor": "active",
    "hedgerow_record": "active",
    "buffer_zone_monitoring": "recorded",
    "landscape_biodiversity_score": "recorded",
}


def _reject_nul(value: object) -> None:
    if isinstance(value, str):
        if "\x00" in value:
            raise LandscapeCaptureInvalid("Text values cannot contain null characters")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_nul(key)
            _reject_nul(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_nul(item)


class LandscapeCaptureInvalid(ValueError):
    """A capture request is malformed or outside its supported bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: object, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise LandscapeCaptureInvalid(f"Invalid {field} identifier") from exc


def _json_object(value: object, field: str, maximum_bytes: int) -> str:
    if not isinstance(value, dict):
        raise LandscapeCaptureInvalid(f"{field} must be an object")
    _reject_nul(value)
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise LandscapeCaptureInvalid(f"{field} must be valid JSON") from exc
    if len(encoded.encode("utf-8")) > maximum_bytes:
        raise LandscapeCaptureInvalid(f"{field} exceeds its size limit")
    return encoded


def create_location_landscape_record(
    operator_id: str,
    location_id: str,
    record_type: str,
    payload: object,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a recorded landscape item via a location-bound SQL contract.

    Expected migration function:
    ``kokonut_security.create_location_landscape_record(
    UUID location_id, TEXT record_type, UUID request_id, JSONB content,
    TEXT reason) RETURNS JSONB``.

    It must check the signed ``landscape_conservation:create`` context, bind
    all habitat references to the requested location, use a private idempotency
    receipt keyed to operator/location/type/request, create the row in its
    source-defined initial state, preserve the legacy defaults/derivations,
    and append audit evidence atomically. Specifically, habitat-zone
    ``gps_boundary_wkt`` must be parsed as valid location-appropriate geometry;
    new wildlife corridors and hedgerows default ``condition`` to ``fair``;
    omitted buffer-check and biodiversity-assessment dates default to the
    database's current date; and ``compliant`` is derived only when both
    buffer and minimum-required widths are supplied. It must never mark a
    record verified or published. Function branches must use static
    table-specific SQL rather than caller-controlled identifiers.
    """
    if record_type not in _INITIAL_STATUS:
        raise LandscapeCaptureInvalid("Landscape record type is not supported")
    if not isinstance(payload, dict):
        raise LandscapeCaptureInvalid("Landscape capture body must be an object")
    if set(payload) != {"request_id", "reason", "content"}:
        raise LandscapeCaptureInvalid("Landscape capture envelope is invalid")

    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    request_id = _uuid(payload["request_id"], "request")
    reason = payload["reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000 or "\x00" in reason:
        raise LandscapeCaptureInvalid("reason must contain 1 to 2000 characters")
    encoded_content = _json_object(payload["content"], "content", 24 * 1024)

    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="landscape_conservation",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.create_location_landscape_record(
                           %s::uuid, %s::text, %s::uuid, %s::jsonb, %s::text
                       )""",
                (
                    location_id,
                    record_type,
                    request_id,
                    encoded_content,
                    reason.strip(),
                ),
            )
            row = cursor.fetchone()
        if not row or row[0] is None:
            raise RuntimeError("Landscape capture returned no record")
        result = row[0]
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise RuntimeError("Landscape capture returned an invalid result")
        expected = {
            "location_id": location_id,
            "record_type": record_type,
            "request_id": request_id,
            "status": _INITIAL_STATUS[record_type],
        }
        for name, value in expected.items():
            if name not in result:
                raise RuntimeError("Landscape capture result is missing request binding")
            actual = _uuid(result[name], name) if name.endswith("_id") else result[name]
            if actual != value:
                raise RuntimeError("Landscape capture result does not match request")
        _uuid(result.get("record_id"), "record")
        if not isinstance(result.get("replayed"), bool):
            raise RuntimeError("Landscape capture replay marker is invalid")
        if not isinstance(result.get("created_at"), str):
            raise RuntimeError("Landscape capture timestamp is invalid")
        connection.commit()
        committed = True
        return result
    finally:
        if not committed:
            connection.rollback()
        connection.close()
