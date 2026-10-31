"""Authenticated location-scoped capture for landscape conservation records.

Every capture is stored in the existing source lifecycle's initial state.
This surface does not verify, publish, or otherwise promote ecological claims.
"""

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

_RequestUUID = Annotated[UUID, BeforeValidator(lambda value: UUID(value) if isinstance(value, str) else value)]
_Measure = StrictInt | StrictFloat


def _reject_nul_characters(value):
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("Text values cannot contain null characters")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_nul_characters(key)
            _reject_nul_characters(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_nul_characters(item)


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _parse_date(value):
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Date must use YYYY-MM-DD") from exc
        if parsed.isoformat() != value:
            raise ValueError("Date must use YYYY-MM-DD")
        return parsed
    raise ValueError("Date must use YYYY-MM-DD")


class _LandscapeCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _RequestUUID
    reason: str = Field(min_length=1, max_length=2000, strict=True)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_shared_fields(self):
        if not self.reason.strip() or "\x00" in self.reason:
            raise ValueError("reason must not be blank or contain null characters")
        try:
            encoded = json.dumps(self.metadata, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("metadata must be a JSON object") from exc
        if len(encoded.encode("utf-8")) > 8 * 1024:
            raise ValueError("metadata exceeds 8 KiB")
        _reject_nul_characters(self.model_dump(mode="python"))
        return self

    @field_validator("metadata", mode="before")
    @classmethod
    def metadata_object(cls, value):
        if not isinstance(value, dict):
            raise ValueError("metadata must be a JSON object")
        return value


class HabitatZoneCaptureRequest(_LandscapeCaptureRequest):
    zone_name: str = Field(min_length=1, max_length=200, strict=True)
    habitat_type: Literal[
        "wetland", "riparian", "forest_patch", "grassland", "hedgerow",
        "orchard", "agroforestry", "other",
    ]
    area_ha: _Measure = Field(ge=0, le=999_999.99)
    biodiversity_value: Literal["low", "medium", "high", "critical"] = "medium"
    perimeter_m: _Measure | None = Field(default=None, ge=0, le=99_999_999.99)
    description: str | None = Field(default=None, max_length=4000, strict=True)
    gps_boundary_wkt: str | None = Field(default=None, max_length=16_000, strict=True)

    @model_validator(mode="after")
    def validate_text(self):
        for value in (self.zone_name, self.description, self.gps_boundary_wkt):
            if value is not None and "\x00" in value:
                raise ValueError("Habitat text cannot contain null characters")
        if not self.zone_name.strip():
            raise ValueError("zone_name must not be blank")
        return self


class WildlifeCorridorCaptureRequest(_LandscapeCaptureRequest):
    corridor_name: str = Field(min_length=1, max_length=200, strict=True)
    source_habitat_id: _RequestUUID | None = None
    target_habitat_id: _RequestUUID | None = None
    width_m: _Measure | None = Field(default=None, ge=0, le=999_999.99)
    length_m: _Measure | None = Field(default=None, ge=0, le=99_999_999.99)
    vegetation_type: str | None = Field(default=None, max_length=100, strict=True)
    notes: str | None = Field(default=None, max_length=4000, strict=True)

    @model_validator(mode="after")
    def validate_text(self):
        for value in (self.corridor_name, self.vegetation_type, self.notes):
            if value is not None and "\x00" in value:
                raise ValueError("Corridor text cannot contain null characters")
        if not self.corridor_name.strip():
            raise ValueError("corridor_name must not be blank")
        return self


class HedgerowCaptureRequest(_LandscapeCaptureRequest):
    hedgerow_name: str | None = Field(default=None, max_length=200, strict=True)
    species_mix: list[str] = Field(default_factory=list, max_length=100)
    length_m: _Measure | None = Field(default=None, ge=0, le=99_999_999.99)
    height_m: _Measure | None = Field(default=None, ge=0, le=999.99)
    age_years: int | None = Field(default=None, ge=0, le=2_147_483_647, strict=True)
    planting_date: date | None = None
    purpose: list[str] = Field(default_factory=list, max_length=100)
    notes: str | None = Field(default=None, max_length=4000, strict=True)

    @field_validator("planting_date", mode="before")
    @classmethod
    def parse_planting_date(cls, value):
        return _parse_date(value)

    @field_validator("species_mix", "purpose")
    @classmethod
    def validate_string_lists(cls, values):
        if any(not isinstance(value, str) or len(value) > 200 or "\x00" in value for value in values):
            raise ValueError("Array entries must be bounded text")
        return [value.strip() for value in values]


class BufferCheckCaptureRequest(_LandscapeCaptureRequest):
    habitat_zone_id: _RequestUUID | None = None
    check_date: date | None = None
    buffer_width_m: _Measure | None = Field(default=None, ge=0, le=999_999.99)
    minimum_required_m: _Measure | None = Field(default=None, ge=0, le=999_999.99)
    vegetation_coverage_pct: _Measure | None = Field(default=None, ge=0, le=100)
    erosion_observed: bool = False
    notes: str | None = Field(default=None, max_length=4000, strict=True)

    @field_validator("check_date", mode="before")
    @classmethod
    def parse_check_date(cls, value):
        return _parse_date(value)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("notes cannot contain null characters")
        return value


class BiodiversityAssessmentCaptureRequest(_LandscapeCaptureRequest):
    assessment_date: date | None = None
    species_richness: int | None = Field(default=None, ge=0, le=2_147_483_647, strict=True)
    shannon_index: _Measure | None = Field(default=None, ge=0, le=99.999)
    habitat_diversity_index: _Measure | None = Field(default=None, ge=0, le=99.999)
    connectivity_score: _Measure | None = Field(default=None, ge=0, le=999.99)
    overall_score: _Measure | None = Field(default=None, ge=0, le=999.99)
    assessor: str | None = Field(default=None, max_length=200, strict=True)
    notes: str | None = Field(default=None, max_length=4000, strict=True)

    @field_validator("assessment_date", mode="before")
    @classmethod
    def parse_assessment_date(cls, value):
        return _parse_date(value)

    @field_validator("assessor", "notes")
    @classmethod
    def validate_optional_text(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("Assessment text cannot contain null characters")
        return value


class LandscapeCaptureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _RequestUUID
    record_id: _RequestUUID
    record_type: Literal[
        "habitat_zone", "wildlife_corridor", "hedgerow_record",
        "buffer_zone_monitoring", "landscape_biodiversity_score",
    ]
    status: Literal["active", "recorded"]
    created_at: AwareDatetime
    request_id: _RequestUUID
    replayed: bool

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("created_at must be an ISO timestamp") from exc
        raise ValueError("created_at must be an ISO timestamp")

    @model_validator(mode="after")
    def status_matches_record_type(self):
        expected = {
            "habitat_zone": "active",
            "wildlife_corridor": "active",
            "hedgerow_record": "active",
            "buffer_zone_monitoring": "recorded",
            "landscape_biodiversity_score": "recorded",
        }[self.record_type]
        if self.status != expected:
            raise ValueError("Capture response status does not match source lifecycle")
        return self


_CAPTURE_ROUTES = (
    (
        "habitats",
        "habitat_zone",
        HabitatZoneCaptureRequest,
    ),
    (
        "corridors",
        "wildlife_corridor",
        WildlifeCorridorCaptureRequest,
    ),
    (
        "hedgerows",
        "hedgerow_record",
        HedgerowCaptureRequest,
    ),
    (
        "buffer-checks",
        "buffer_zone_monitoring",
        BufferCheckCaptureRequest,
    ),
    (
        "biodiversity-assessments",
        "landscape_biodiversity_score",
        BiodiversityAssessmentCaptureRequest,
    ),
)


def register_landscape_conservation_mutation_routes(router, provider, run_in_threadpool, psycopg2):
    import json as json_module

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.landscape_conservation_writes import (
        LandscapeCaptureInvalid,
        create_location_landscape_record,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    async def bounded_payload(request: Request):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 32 * 1024:
                    return None, JSONResponse(
                        status_code=413,
                        content={"error": "Landscape capture body exceeds 32 KiB"},
                        headers=headers,
                    )
            except ValueError:
                return None, JSONResponse(
                    status_code=400,
                    content={"error": "Invalid content length"},
                    headers=headers,
                )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 32 * 1024:
                return None, JSONResponse(
                    status_code=413,
                    content={"error": "Landscape capture body exceeds 32 KiB"},
                    headers=headers,
                )
        try:
            payload = json_module.loads(body, object_pairs_hook=_unique_json_object)
        except (ValueError, RecursionError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Landscape capture body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Landscape capture body must be an object"},
                headers=headers,
            )
        return payload, None

    def register_capture(path_suffix: str, record_type: str, request_model):
        async def capture(request: Request, location_id: str):
            if provider is None:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Operator OIDC is disabled"},
                    headers=headers,
                )
            payload, body_error = await bounded_payload(request)
            if body_error is not None:
                return body_error
            try:
                requested_location = UUID(location_id)
                capture_request = request_model.model_validate(payload)
            except (TypeError, ValueError, ValidationError):
                return JSONResponse(
                    status_code=400,
                    content={"error": "Landscape capture request is invalid"},
                    headers=headers,
                )
            request_payload = {
                "request_id": str(capture_request.request_id),
                "reason": capture_request.reason,
                "content": capture_request.model_dump(
                    mode="json", exclude={"request_id", "reason"}
                ),
            }
            try:
                result = await run_in_threadpool(
                    create_location_landscape_record,
                    request.state.operator_session.operator.operator_id,
                    str(requested_location),
                    record_type,
                    request_payload,
                )
            except TenantContextDenied:
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact-location landscape create grant is required"},
                    headers=headers,
                )
            except LandscapeCaptureInvalid as exc:
                return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
            except psycopg2.Error as exc:
                code = getattr(exc, "pgcode", None)
                if code == "42501":
                    return JSONResponse(
                        status_code=403,
                        content={"error": "A current exact-location landscape create grant is required"},
                        headers=headers,
                    )
                if code == "22023":
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Landscape capture input is invalid or outside its bounds"},
                        headers=headers,
                    )
                if code == "23505":
                    return JSONResponse(
                        status_code=409,
                        content={"error": "The request ID was already used with different input"},
                        headers=headers,
                    )
                from services.common.logging import get_logger

                get_logger("gateway.landscape").warning(
                    "Landscape capture unavailable (%s)", type(exc).__name__
                )
                return JSONResponse(
                    status_code=503,
                    content={"error": "Landscape capture unavailable"},
                    headers={**headers, "Retry-After": "30"},
                )
            except Exception as exc:
                from services.common.logging import get_logger

                get_logger("gateway.landscape").warning(
                    "Landscape capture contract failed (%s)", type(exc).__name__
                )
                return JSONResponse(
                    status_code=500,
                    content={"error": "Landscape capture unavailable"},
                    headers=headers,
                )
            try:
                response = LandscapeCaptureResponse.model_validate(result)
                if (
                    response.location_id != requested_location
                    or response.record_type != record_type
                    or response.request_id != capture_request.request_id
                ):
                    raise ValueError("Landscape response does not match request")
            except (TypeError, ValueError, ValidationError) as exc:
                from services.common.logging import get_logger

                get_logger("gateway.landscape").warning(
                    "Landscape capture response rejected (%s)", type(exc).__name__
                )
                return JSONResponse(
                    status_code=500,
                    content={"error": "Landscape capture unavailable"},
                    headers=headers,
                )
            return JSONResponse(
                jsonable_encoder(response.model_dump(mode="json")),
                status_code=200 if response.replayed else 201,
                headers=headers,
            )

        request_schema = request_model.model_json_schema()
        router.add_api_route(
            f"/operator/api/landscape/{{location_id}}/{path_suffix}",
            capture,
            methods=["POST"],
            name=f"capture_landscape_{record_type}",
            response_model=LandscapeCaptureResponse,
            status_code=201,
            responses={
                200: {"model": LandscapeCaptureResponse, "description": "Idempotent replay"},
                400: {"description": "Invalid capture request"},
                403: {"description": "Exact-location landscape create grant required"},
                409: {"description": "Request ID was reused with different content"},
                413: {"description": "Request body exceeds 32 KiB"},
                500: {"description": "Capture receipt failed validation"},
                503: {"description": "Landscape capture unavailable"},
            },
            openapi_extra={
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": request_schema}},
                }
            },
        )

    for suffix, record_type, model in _CAPTURE_ROUTES:
        register_capture(suffix, record_type, model)
