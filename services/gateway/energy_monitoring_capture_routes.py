"""Authenticated location-scoped energy-reading capture routes."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)
from starlette.requests import Request

_Number = StrictInt | StrictFloat
_RequestUUID = Annotated[
    UUID, BeforeValidator(lambda value: UUID(value) if isinstance(value, str) else value)
]


def _strict_date(value):
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("reading_date must use YYYY-MM-DD") from exc
        if result.isoformat() == value:
            return result
    raise ValueError("reading_date must use YYYY-MM-DD")


def _reject_nul(value):
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("text values must not contain null characters")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_nul(key)
            _reject_nul(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_nul(item)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


class EnergyReadingCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _RequestUUID
    source_id: _RequestUUID
    reading_date: date | None = None
    reading_type: Literal["consumption", "production"]
    kwh: _Number = Field(ge=-99_999_999.99, le=99_999_999.99)
    cost_per_kwh: _Number | None = Field(default=None, ge=-9_999.9999, le=9_999.9999)
    cost_currency_code: str | None = Field(default=None, min_length=3, max_length=3, strict=True)
    activity_type: Literal[
        "irrigation", "processing", "storage", "lighting", "pump", "other"
    ] | None = None
    equipment_id: _RequestUUID | None = None
    notes: str | None = Field(default=None, max_length=2000, strict=True)
    metadata: dict = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=2000, strict=True)

    @field_validator("reading_date", mode="before")
    @classmethod
    def parse_reading_date(cls, value):
        return _strict_date(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def metadata_object(cls, value):
        if not isinstance(value, dict):
            raise ValueError("metadata must be an object")
        return value

    @field_validator("cost_currency_code", mode="before")
    @classmethod
    def normalize_cost_currency(cls, value):
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_capture(self):
        if self.cost_per_kwh is None and self.cost_currency_code is not None:
            raise ValueError("cost_currency_code requires cost_per_kwh")
        if self.cost_per_kwh is not None:
            if self.cost_currency_code is None or not self.cost_currency_code.isascii() or not self.cost_currency_code.isalpha():
                raise ValueError("cost_currency_code must contain three ASCII letters")
            if self.cost_currency_code != self.cost_currency_code.upper():
                raise ValueError("cost_currency_code must be uppercase")
        if not self.reason.strip() or "\x00" in self.reason:
            raise ValueError("reason must not be blank or contain null characters")
        if self.notes is not None and "\x00" in self.notes:
            raise ValueError("notes must not contain null characters")
        try:
            encoded = json.dumps(self.metadata, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("metadata must be valid JSON") from exc
        if len(encoded.encode("utf-8")) > 16 * 1024:
            raise ValueError("metadata exceeds 16 KiB")
        _reject_nul(self.model_dump(mode="python"))
        return self


class EnergyReadingCaptureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _RequestUUID
    reading_id: _RequestUUID
    location_id: _RequestUUID
    source_id: _RequestUUID
    reading_date: date
    reading_type: Literal["consumption", "production"]
    kwh: _Number
    cost_per_kwh: _Number | None
    total_cost: _Number | None
    cost_currency_code: str | None
    activity_type: Literal[
        "irrigation", "processing", "storage", "lighting", "pump", "other"
    ] | None
    status: Literal["recorded"]
    replayed: bool
    created_at: AwareDatetime

    @field_validator("reading_date", mode="before")
    @classmethod
    def parse_response_reading_date(cls, value):
        return _strict_date(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("created_at must be timezone-aware") from exc
        raise ValueError("created_at must be timezone-aware")


def register_energy_monitoring_capture_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.energy_monitoring_writes import (
        EnergyReadingCaptureInvalid,
        record_location_energy_reading,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    async def capture_energy_reading(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 32 * 1024:
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Energy reading body exceeds 32 KiB"},
                        headers=headers,
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid content length"},
                    headers=headers,
                )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 32 * 1024:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Energy reading body exceeds 32 KiB"},
                    headers=headers,
                )
        try:
            raw_payload = json.loads(body, object_pairs_hook=_unique_object)
        except (ValueError, RecursionError):
            return JSONResponse(
                status_code=400,
                content={"error": "Energy reading body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(raw_payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Energy reading body must be an object"},
                headers=headers,
            )
        try:
            requested_location = UUID(location_id)
            capture = EnergyReadingCaptureRequest.model_validate(raw_payload)
        except (TypeError, ValueError, ValidationError):
            return JSONResponse(
                status_code=400,
                content={"error": "Energy reading request is invalid"},
                headers=headers,
            )

        effective_reading_date = capture.reading_date or date.today()
        payload = capture.model_dump(mode="json")
        payload["reading_date"] = effective_reading_date.isoformat()
        try:
            result = await run_in_threadpool(
                record_location_energy_reading,
                request.state.operator_session.operator.operator_id,
                str(requested_location),
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "A current exact-location energy create grant is required"},
                headers=headers,
            )
        except EnergyReadingCaptureInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact-location energy create grant is required"},
                    headers=headers,
                )
            if code in {"22023", "22003", "23514", "22001"}:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Energy reading input is invalid or outside its bounds"},
                    headers=headers,
                )
            if code == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.energy").warning(
                "Energy reading capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Energy reading capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.energy").warning(
                "Energy reading capture contract failed (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Energy reading capture unavailable"},
                headers=headers,
            )

        try:
            response = EnergyReadingCaptureResponse.model_validate(result)
            if (
                response.location_id != requested_location
                or response.request_id != capture.request_id
                or response.source_id != capture.source_id
                or response.reading_date != effective_reading_date
            ):
                raise ValueError("Energy reading receipt does not match the request")
        except (TypeError, ValueError, ValidationError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.energy").warning(
                "Energy reading capture response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Energy reading capture unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="json")),
            status_code=200 if response.replayed else 201,
            headers=headers,
        )

    router.add_api_route(
        "/operator/api/energy/{location_id}/readings",
        capture_energy_reading,
        methods=["POST"],
        name="capture_energy_reading",
        response_model=EnergyReadingCaptureResponse,
        status_code=201,
        responses={
            200: {"model": EnergyReadingCaptureResponse, "description": "Idempotent replay"},
            400: {"description": "Invalid capture request"},
            403: {"description": "Exact-location energy create grant required"},
            409: {"description": "Request ID was reused with different content"},
            413: {"description": "Request body exceeds 32 KiB"},
            500: {"description": "Capture receipt failed validation"},
            503: {"description": "Energy reading capture unavailable"},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": EnergyReadingCaptureRequest.model_json_schema()
                    }
                },
            }
        },
    )
