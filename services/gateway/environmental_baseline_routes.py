"""Authenticated, location-scoped environmental-baseline capture route."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from starlette.requests import Request

from services.gateway.environmental_baseline_contracts import (
    EnvironmentalBaselineCaptureRequest,
    EnvironmentalBaselineCaptureResponse,
)

_HEADERS = {"Cache-Control": "no-store", "Vary": "Cookie"}
_MAX_BODY_BYTES = 32 * 1024


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object contains a duplicate key")
        result[key] = value
    return result


def register_environmental_baseline_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.environmental_baseline_writes import (
        EnvironmentalBaselineCaptureInvalid,
        capture_location_environmental_baseline,
    )

    def _error(status: int, message: str, *, retry_after: bool = False):
        headers = dict(_HEADERS)
        if retry_after:
            headers["Retry-After"] = "30"
        return JSONResponse(status_code=status, content={"error": message}, headers=headers)

    async def capture_environmental_baseline(request: Request, location_id: str):
        if provider is None:
            return _error(404, "Operator OIDC is disabled")
        try:
            requested_location = UUID(location_id)
        except (TypeError, ValueError, AttributeError):
            return _error(400, "Location identifier is invalid")

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > _MAX_BODY_BYTES:
                    return _error(413, "Environmental baseline body exceeds 32 KiB")
            except ValueError:
                return _error(400, "Content length is invalid")

        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > _MAX_BODY_BYTES:
                return _error(413, "Environmental baseline body exceeds 32 KiB")
        try:
            raw_payload = json.loads(body, object_pairs_hook=_unique_json_object)
        except (ValueError, RecursionError):
            return _error(400, "Environmental baseline body must be valid JSON")
        if not isinstance(raw_payload, dict):
            return _error(400, "Environmental baseline body must be an object")
        try:
            capture = EnvironmentalBaselineCaptureRequest.model_validate(raw_payload)
        except ValidationError:
            return _error(400, "Environmental baseline request is invalid")

        try:
            result = await run_in_threadpool(
                capture_location_environmental_baseline,
                request.state.operator_session.operator.operator_id,
                str(requested_location),
                capture.model_dump(mode="json"),
            )
        except TenantContextDenied:
            return _error(403, "A current exact-location environmental-baseline create grant is required")
        except EnvironmentalBaselineCaptureInvalid:
            return _error(400, "Environmental baseline request is invalid or outside its bounds")
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return _error(403, "A current exact-location environmental-baseline create grant is required")
            if code in {"22023", "22003", "23514", "22001"}:
                return _error(400, "Environmental baseline request is invalid or outside its bounds")
            if code in {"P0001", "23505"}:
                return _error(409, "Request ID was already used with different input")
            from services.common.logging import get_logger

            get_logger("gateway.environmental_baseline").warning(
                "Environmental baseline capture unavailable (%s)", type(exc).__name__
            )
            return _error(503, "Environmental baseline capture unavailable", retry_after=True)
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.environmental_baseline").warning(
                "Environmental baseline capture failed (%s)", type(exc).__name__
            )
            return _error(500, "Environmental baseline capture unavailable")

        try:
            response = EnvironmentalBaselineCaptureResponse.model_validate(result)
            if (
                response.location_id != requested_location
                or response.plot_id != capture.plot_id
                or response.metric_name != capture.metric_name
                or response.baseline_value != Decimal(str(capture.baseline_value))
                or response.unit != capture.unit
                or response.measurement_date != capture.measurement_date
                or response.measurement_method != capture.measurement_method
                or response.source != capture.source
            ):
                raise ValueError("baseline receipt does not match request")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.environmental_baseline").warning(
                "Environmental baseline receipt rejected (%s)", type(exc).__name__
            )
            return _error(500, "Environmental baseline capture unavailable")
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="json")),
            status_code=200 if response.replayed else 201,
            headers=_HEADERS,
        )

    router.add_api_route(
        "/operator/api/environmental-baselines/{location_id}/captures",
        capture_environmental_baseline,
        methods=["POST"],
        name="capture_environmental_baseline",
        response_model=EnvironmentalBaselineCaptureResponse,
        status_code=201,
        responses={
            200: {"model": EnvironmentalBaselineCaptureResponse, "description": "Idempotent replay"},
            400: {"description": "Invalid or out-of-bounds capture request"},
            403: {"description": "Exact-location environmental-baseline create grant required"},
            409: {"description": "Request ID was reused with different content"},
            413: {"description": "Request body exceeds 32 KiB"},
            500: {"description": "Bounded database receipt failed validation"},
            503: {"description": "Capture service is unavailable"},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": EnvironmentalBaselineCaptureRequest.model_json_schema()
                    }
                },
            }
        },
    )
