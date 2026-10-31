"""Location-scoped metric writes through bounded security functions.

No direct ``metric_value`` INSERT or UPDATE is issued here. The final
migration must provide these JSONB-returning functions:

* ``kokonut_security.create_location_metric_value_draft(UUID location_id,
  UUID request_id, UUID metric_definition_id, TEXT metric_key, DATE
  period_start, DATE period_end, NUMERIC value, TEXT unit, TEXT
  computation_method, UUID[] source_record_ids, JSONB metadata)``. It must
  require signed ``metric_value:compute`` context; confirm the active metric
  definition and exact location scope; create only ``verified = FALSE`` rows;
  bind request receipts to canonical input; and atomically preserve the
  original receipt on an identical retry while rejecting a changed-payload
  collision. It returns exactly the fields in
  :class:`MetricValueComputeResponse`.
* ``kokonut_security.verify_location_metric_value(UUID location_id, UUID
  metric_value_id, UUID request_id, TEXT verification_notes)``. It must require
  signed ``metric_value:verify`` context, match the draft to ``location_id``,
  derive ``verified_by`` from the authenticated operator in that context (the
  request never supplies reviewer identity), reject self-review against the
  private compute receipt, atomically persist the verification and replay
  receipt, and return exactly the fields in
  :class:`MetricValueVerifyResponse` without exposing reviewer identity.

Both functions must reject direct caller-selected SQL identifiers, verify the
active operator grant in the same transaction, use a serialization-safe
idempotency key, and leave transaction ownership to this helper.

Stable function errors are ``42501`` for a missing/invalid signed grant,
``P0002`` when the requested metric definition or value is unavailable, and
``P0001`` for an idempotency collision, self-review, or invalid lifecycle
transition. Other SQL errors remain unavailable-service failures.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import TenantContextDenied, set_operator_tenant_context
from services.gateway.metric_value_contracts import (
    MetricValueComputeResponse,
    MetricValueVerifyResponse,
)


class MetricValueWriteInvalid(ValueError):
    """The metric operation request is malformed or unsupported."""


class MetricValueWriteConflict(RuntimeError):
    """The operation conflicts with an existing metric receipt or lifecycle."""


class MetricValueWriteNotFound(LookupError):
    """The requested metric definition/value is unavailable in this location."""


class MetricValueWriteReceiptInvalid(RuntimeError):
    """A bounded SQL function returned a malformed or misbound receipt."""


def _reject_nul(value: object) -> None:
    if isinstance(value, str):
        if "\x00" in value:
            raise MetricValueWriteInvalid("Metric metadata cannot contain null characters")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_nul(key)
            _reject_nul(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_nul(item)


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: object, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise MetricValueWriteInvalid(f"Invalid {label} identifier") from exc


def _json_receipt(row, function_name: str) -> dict:
    if row is None or not row[0]:
        raise MetricValueWriteNotFound("Metric operation did not return a receipt")
    receipt = row[0]
    if isinstance(receipt, str):
        try:
            receipt = json.loads(receipt)
        except (TypeError, ValueError, RecursionError) as exc:
            raise MetricValueWriteReceiptInvalid(
                f"{function_name} returned invalid JSON"
            ) from exc
    if not isinstance(receipt, dict):
        raise MetricValueWriteReceiptInvalid(
            f"{function_name} returned a non-object receipt"
        )
    return receipt


def _raise_function_error(exc) -> None:
    """Translate the bounded RPC's documented SQLSTATEs without leaking SQL."""
    sqlstate = getattr(exc, "pgcode", None)
    if sqlstate == "42501":
        raise TenantContextDenied("Metric operation requires a current location grant") from exc
    if sqlstate == "P0002":
        raise MetricValueWriteNotFound("Metric object is unavailable in this location") from exc
    if sqlstate == "P0001":
        raise MetricValueWriteConflict("Metric request conflicts with existing state") from exc
    if sqlstate in {"22003", "22023", "23514"}:
        raise MetricValueWriteInvalid("Metric function rejected invalid input") from exc
    if sqlstate == "23505":
        raise MetricValueWriteConflict("Metric request conflicts with existing state") from exc
    raise exc


def _validated_draft(draft: dict, location_id: str, metric_key: str) -> dict:
    """Reject malformed calculator output before passing it to a SQL function."""
    if draft.get("location_id") != location_id or draft.get("metric_key") != metric_key:
        raise MetricValueWriteInvalid("Metric calculation returned mismatched scope")
    draft["metric_id"] = _uuid(draft.get("metric_id"), "metric definition")

    value = draft.get("value")
    if value is not None:
        if isinstance(value, bool):
            raise MetricValueWriteInvalid("Metric calculation returned a non-numeric value")
        try:
            value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise MetricValueWriteInvalid(
                "Metric calculation returned a non-numeric value"
            ) from exc
        if not value.is_finite() or abs(value) > Decimal("99999999999.9999"):
            raise MetricValueWriteInvalid("Metric calculation returned an out-of-range value")
    draft["value"] = value

    unit = draft.get("unit")
    if unit is not None and (
        not isinstance(unit, str) or len(unit) > 50 or "\x00" in unit
    ):
        raise MetricValueWriteInvalid("Metric definition returned an invalid unit")

    method = draft.get("computation_method")
    if (
        not isinstance(method, str)
        or not method.strip()
        or len(method) > 100
        or "\x00" in method
    ):
        raise MetricValueWriteInvalid("Metric calculation returned an invalid method")
    draft["computation_method"] = method.strip()

    source_record_ids = draft.get("source_record_ids")
    if not isinstance(source_record_ids, list):
        raise MetricValueWriteInvalid("Metric calculation returned invalid source references")
    if len(source_record_ids) > 100_000:
        raise MetricValueWriteInvalid("Metric calculation returned too many source references")
    draft["source_record_ids"] = [
        _uuid(source_id, "source record") for source_id in source_record_ids
    ]

    metadata = draft.get("metadata")
    if not isinstance(metadata, dict):
        raise MetricValueWriteInvalid("Metric calculation returned invalid metadata")
    _reject_nul(metadata)
    try:
        encoded = json.dumps(metadata, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise MetricValueWriteInvalid("Metric calculation returned invalid metadata") from exc
    if len(encoded.encode("utf-8")) > 24 * 1024:
        raise MetricValueWriteInvalid("Metric metadata exceeds 24 KiB")
    return draft


def create_location_metric_value_draft(
    operator_id: str,
    location_id: str,
    request_id: str,
    metric_key: str,
    period_start=None,
    period_end=None,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Calculate one location metric and persist it through its bounded RPC."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    request_id = _uuid(request_id, "request")
    if (
        not isinstance(metric_key, str)
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", metric_key.strip())
    ):
        raise MetricValueWriteInvalid("metric_key is required")
    metric_key = metric_key.strip()
    if period_start is not None and period_end is not None and period_start > period_end:
        raise MetricValueWriteInvalid("period_start must not be after period_end")

    from services.metrics.engine import compute_metric_draft

    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="metric_value",
            action="compute",
        )
        draft = compute_metric_draft(
            connection,
            metric_key,
            location_id,
            period_start,
            period_end,
        )
        if "error" in draft:
            message = str(draft["error"])
            if "not found or inactive" in message or "No calculator registered" in message:
                raise MetricValueWriteNotFound("Metric definition is unavailable")
            raise MetricValueWriteInvalid("Metric calculation could not produce a draft")

        draft = _validated_draft(draft, location_id, metric_key)
        metadata = draft["metadata"]
        source_record_ids = draft["source_record_ids"]
        try:
            metadata_json = json.dumps(
                metadata, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError, RecursionError) as exc:
            raise MetricValueWriteInvalid(
                "Metric calculation returned invalid metadata"
            ) from exc
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    """SELECT kokonut_security.create_location_metric_value_draft(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::date,
                           %s::date, %s::numeric, %s::text, %s::text,
                           %s::uuid[], %s::jsonb
                       )""",
                    (
                        location_id,
                        request_id,
                        draft["metric_id"],
                        draft["metric_key"],
                        period_start,
                        period_end,
                        draft["value"],
                        draft["unit"],
                        draft["computation_method"],
                        source_record_ids,
                        metadata_json,
                    ),
                )
            except Exception as exc:
                _raise_function_error(exc)
            receipt = _json_receipt(
                cursor.fetchone(), "create_location_metric_value_draft"
            )
        try:
            validated = MetricValueComputeResponse.model_validate(receipt)
        except Exception as exc:
            raise MetricValueWriteReceiptInvalid(
                "Metric draft receipt failed contract validation"
            ) from exc
        if (
            validated.location_id != UUID(location_id)
            or validated.request_id != UUID(request_id)
            or validated.metric_key != draft["metric_key"]
            or validated.period_start != period_start
            or validated.period_end != period_end
        ):
            raise MetricValueWriteReceiptInvalid(
                "Metric draft receipt does not match its request"
            )
        connection.commit()
        committed = True
        return validated.model_dump(mode="json")
    finally:
        if not committed:
            connection.rollback()
        connection.close()


def verify_location_metric_value(
    operator_id: str,
    location_id: str,
    metric_value_id: str,
    request_id: str,
    verification_notes: str | None = None,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Verify a location draft; reviewer identity comes only from session context."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    metric_value_id = _uuid(metric_value_id, "metric value")
    request_id = _uuid(request_id, "request")
    if verification_notes is not None:
        if not isinstance(verification_notes, str) or "\x00" in verification_notes:
            raise MetricValueWriteInvalid("verification_notes must be safe text")
        verification_notes = verification_notes.strip() or None
        if verification_notes is not None and len(verification_notes) > 2000:
            raise MetricValueWriteInvalid("verification_notes exceeds 2000 characters")

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
            resource="metric_value",
            action="verify",
        )
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    """SELECT kokonut_security.verify_location_metric_value(
                           %s::uuid, %s::uuid, %s::uuid, %s::text
                       )""",
                    (location_id, metric_value_id, request_id, verification_notes),
                )
            except Exception as exc:
                _raise_function_error(exc)
            receipt = _json_receipt(
                cursor.fetchone(), "verify_location_metric_value"
            )
        try:
            validated = MetricValueVerifyResponse.model_validate(receipt)
        except Exception as exc:
            raise MetricValueWriteReceiptInvalid(
                "Metric verification receipt failed contract validation"
            ) from exc
        if (
            validated.location_id != UUID(location_id)
            or validated.metric_value_id != UUID(metric_value_id)
            or validated.request_id != UUID(request_id)
        ):
            raise MetricValueWriteReceiptInvalid(
                "Metric verification receipt does not match its request"
            )
        connection.commit()
        committed = True
        return validated.model_dump(mode="json")
    finally:
        if not committed:
            connection.rollback()
        connection.close()
