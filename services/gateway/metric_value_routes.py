"""Authenticated location-scoped metric computation and verification routes."""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError
from starlette.requests import Request

from services.gateway.metric_value_contracts import (
    MetricValueComputeRequest,
    MetricValueComputeResponse,
    MetricValueListResponse,
    MetricValueVerifyRequest,
    MetricValueVerifyResponse,
)

_HEADERS = {"Cache-Control": "no-store", "Vary": "Cookie"}
_MAX_BODY_BYTES = 16 * 1024


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object contains a duplicate key")
        result[key] = value
    return result


async def _request_object(request):
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _MAX_BODY_BYTES:
            return None, 413
        body.extend(chunk)
    try:
        value = json.loads(body, object_pairs_hook=_unique_json_object)
    except (ValueError, RecursionError):
        return None, 400
    if not isinstance(value, dict):
        return None, 400
    return value, None


def register_metric_value_routes(router, provider, run_in_threadpool, psycopg2):
    """Register draft computation and separate human verification endpoints."""
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.metric_value_reads import (
        MetricValueReadInvalid,
        MetricValueReadNotFound,
        MetricValueReadReceiptInvalid,
        list_location_metric_values,
    )
    from services.gateway.metric_value_writes import (
        MetricValueWriteConflict,
        MetricValueWriteInvalid,
        MetricValueWriteNotFound,
        MetricValueWriteReceiptInvalid,
        create_location_metric_value_draft,
        verify_location_metric_value,
    )

    def _error(status: int, message: str, *, retry_after: bool = False):
        headers = dict(_HEADERS)
        if retry_after:
            headers["Retry-After"] = "30"
        return JSONResponse(status_code=status, content={"error": message}, headers=headers)

    def _validate_location(location_id: str):
        try:
            return UUID(location_id)
        except (TypeError, ValueError, AttributeError):
            return None

    def _read_page_parameters(request: Request):
        if set(request.query_params.keys()) - {"cursor", "limit"}:
            return None
        cursors = request.query_params.getlist("cursor")
        limits = request.query_params.getlist("limit")
        if len(cursors) > 1 or len(limits) > 1:
            return None
        cursor = cursors[0] if cursors else "0"
        raw_limit = limits[0] if limits else "25"
        if (
            not isinstance(cursor, str)
            or len(cursor) > 5
            or not cursor.isascii()
            or not cursor.isdecimal()
            or (cursor != "0" and cursor.startswith("0"))
            or int(cursor) > 10_000
        ):
            return None
        if (
            not isinstance(raw_limit, str)
            or not raw_limit.isascii()
            or not raw_limit.isdecimal()
            or (raw_limit != "0" and raw_limit.startswith("0"))
        ):
            return None
        limit = int(raw_limit)
        if not 1 <= limit <= 100:
            return None
        return cursor, limit

    def _database_unavailable(operation: str, exc):
        from services.common.logging import get_logger

        get_logger("gateway.metric_value").warning(
            "%s unavailable (%s)", operation, type(exc).__name__
        )
        return _error(503, "Metric operation unavailable", retry_after=True)

    @router.get(
        "/operator/api/metrics/{location_id}/values",
        response_model=MetricValueListResponse,
        responses={
            200: {
                "model": MetricValueListResponse,
                "description": "An identity-minimized metric review page for one location.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            400: {"description": "Cursor, limit, or location is invalid."},
            403: {"description": "The operator lacks the exact location read grant."},
            404: {"description": "Operator OIDC or the metric list is unavailable."},
            500: {"description": "The bounded database page failed response validation."},
            503: {"description": "Metric list is unavailable."},
        },
        openapi_extra={
            "parameters": [
                {
                    "name": "cursor",
                    "in": "query",
                    "required": False,
                    "schema": {
                        "type": "string",
                        "pattern": "^(0|[1-9][0-9]*)$",
                        "maxLength": 5,
                        "default": "0",
                    },
                },
                {
                    "name": "limit",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25},
                },
            ]
        },
    )
    async def list_location_metrics_route(request: Request, location_id: str):
        if provider is None:
            return _error(404, "Operator OIDC is disabled")
        requested_location = _validate_location(location_id)
        if requested_location is None:
            return _error(400, "Location identifier is invalid")
        page_parameters = _read_page_parameters(request)
        if page_parameters is None:
            return _error(400, "Metric page cursor or limit is invalid")
        cursor, limit = page_parameters
        try:
            result = await run_in_threadpool(
                list_location_metric_values,
                request.state.operator_session.operator.operator_id,
                str(requested_location),
                cursor,
                limit,
            )
        except TenantContextDenied:
            return _error(403, "Tenant-qualified metric read access is required")
        except MetricValueReadInvalid:
            return _error(400, "Metric page request is invalid")
        except MetricValueReadNotFound:
            return _error(404, "Metric list is unavailable")
        except psycopg2.Error as exc:
            return _database_unavailable("Metric list", exc)
        except MetricValueReadReceiptInvalid as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").warning(
                "Metric list receipt rejected (%s)", type(exc).__name__
            )
            return _error(500, "Metric list unavailable")
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").error(
                "Metric list failed (%s)", type(exc).__name__
            )
            return _error(500, "Metric list unavailable")

        try:
            page = MetricValueListResponse.model_validate(result)
            if page.location_id != requested_location or page.cursor != cursor or page.limit != limit:
                raise ValueError("metric page binding mismatch")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").warning(
                "Metric list response rejected (%s)", type(exc).__name__
            )
            return _error(500, "Metric list unavailable")
        return JSONResponse(
            content=jsonable_encoder(page.model_dump(mode="json")),
            headers=_HEADERS,
        )

    @router.post(
        "/operator/api/metrics/{location_id}/values",
        response_model=MetricValueComputeResponse,
        responses={
            201: {
                "model": MetricValueComputeResponse,
                "description": "A new unverified metric draft was computed.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            200: {
                "model": MetricValueComputeResponse,
                "description": "The original metric draft receipt was replayed.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            400: {"description": "The request or metric calculation is invalid."},
            403: {"description": "The operator lacks the location-scoped compute grant."},
            404: {"description": "Operator OIDC or the active metric is unavailable."},
            409: {"description": "The idempotency key conflicts with prior input."},
            413: {"description": "The request body exceeds 16 KiB."},
            500: {"description": "The bounded database receipt is malformed."},
            503: {"description": "Metric computation is unavailable."},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": MetricValueComputeRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def compute_location_metric_route(request: Request, location_id: str):
        if provider is None:
            return _error(404, "Operator OIDC is disabled")
        requested_location = _validate_location(location_id)
        if requested_location is None:
            return _error(400, "Location identifier is invalid")
        payload, status = await _request_object(request)
        if status == 413:
            return _error(413, "Metric request exceeds 16 KiB")
        if status is not None:
            return _error(400, "Metric computation request is invalid")
        try:
            command = MetricValueComputeRequest.model_validate(payload)
        except ValidationError:
            return _error(400, "Metric computation request is invalid")

        try:
            result = await run_in_threadpool(
                create_location_metric_value_draft,
                request.state.operator_session.operator.operator_id,
                str(requested_location),
                str(command.request_id),
                command.metric_key,
                command.period_start,
                command.period_end,
            )
        except TenantContextDenied:
            return _error(403, "Tenant-qualified metric access is required")
        except MetricValueWriteInvalid:
            return _error(400, "Metric computation request is invalid")
        except MetricValueWriteNotFound:
            return _error(404, "Metric definition is unavailable")
        except MetricValueWriteConflict:
            return _error(409, "Metric request conflicts with existing state")
        except psycopg2.Error as exc:
            return _database_unavailable("Metric computation", exc)
        except MetricValueWriteReceiptInvalid as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").warning(
                "Metric computation receipt rejected (%s)", type(exc).__name__
            )
            return _error(500, "Metric computation unavailable")
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").error(
                "Metric computation failed (%s)", type(exc).__name__
            )
            return _error(500, "Metric computation unavailable")

        try:
            receipt = MetricValueComputeResponse.model_validate(result)
            if (
                receipt.location_id != requested_location
                or receipt.request_id != command.request_id
                or receipt.metric_key != command.metric_key
                or receipt.period_start != command.period_start
                or receipt.period_end != command.period_end
            ):
                raise ValueError("metric draft receipt binding mismatch")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").warning(
                "Metric computation response rejected (%s)", type(exc).__name__
            )
            return _error(500, "Metric computation unavailable")
        return JSONResponse(
            status_code=201 if receipt.created else 200,
            content=jsonable_encoder(receipt.model_dump(mode="json")),
            headers=_HEADERS,
        )

    @router.post(
        "/operator/api/metrics/{location_id}/values/{metric_value_id}/verify",
        response_model=MetricValueVerifyResponse,
        responses={
            200: {
                "model": MetricValueVerifyResponse,
                "description": "The metric was verified or an existing decision replayed.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            400: {"description": "The request is invalid."},
            403: {"description": "The operator lacks the separate verify grant."},
            404: {"description": "The draft is unavailable in this location."},
            409: {"description": "The draft is already decided or the request conflicts."},
            413: {"description": "The request body exceeds 16 KiB."},
            500: {"description": "The bounded database receipt is malformed."},
            503: {"description": "Metric verification is unavailable."},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": MetricValueVerifyRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def verify_location_metric_route(
        request: Request, location_id: str, metric_value_id: str
    ):
        if provider is None:
            return _error(404, "Operator OIDC is disabled")
        requested_location = _validate_location(location_id)
        try:
            requested_value = UUID(metric_value_id)
        except (TypeError, ValueError, AttributeError):
            requested_value = None
        if requested_location is None or requested_value is None:
            return _error(400, "Metric identifier is invalid")
        payload, status = await _request_object(request)
        if status == 413:
            return _error(413, "Metric verification request exceeds 16 KiB")
        if status is not None:
            return _error(400, "Metric verification request is invalid")
        try:
            command = MetricValueVerifyRequest.model_validate(payload)
        except ValidationError:
            return _error(400, "Metric verification request is invalid")

        try:
            result = await run_in_threadpool(
                verify_location_metric_value,
                request.state.operator_session.operator.operator_id,
                str(requested_location),
                str(requested_value),
                str(command.request_id),
                command.verification_notes,
            )
        except TenantContextDenied:
            return _error(403, "Tenant-qualified metric review is required")
        except MetricValueWriteInvalid:
            return _error(400, "Metric verification request is invalid")
        except MetricValueWriteNotFound:
            return _error(404, "Metric draft is unavailable")
        except MetricValueWriteConflict:
            return _error(409, "Metric draft cannot be verified in its current state")
        except psycopg2.Error as exc:
            return _database_unavailable("Metric verification", exc)
        except MetricValueWriteReceiptInvalid as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").warning(
                "Metric verification receipt rejected (%s)", type(exc).__name__
            )
            return _error(500, "Metric verification unavailable")
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").error(
                "Metric verification failed (%s)", type(exc).__name__
            )
            return _error(500, "Metric verification unavailable")

        try:
            receipt = MetricValueVerifyResponse.model_validate(result)
            if (
                receipt.location_id != requested_location
                or receipt.metric_value_id != requested_value
                or receipt.request_id != command.request_id
            ):
                raise ValueError("metric verification receipt binding mismatch")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.metric_value").warning(
                "Metric verification response rejected (%s)", type(exc).__name__
            )
            return _error(500, "Metric verification unavailable")
        return JSONResponse(
            content=jsonable_encoder(receipt.model_dump(mode="json")),
            headers=_HEADERS,
        )
