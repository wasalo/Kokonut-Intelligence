"""OIDC routes for location-scoped waste summaries and capture."""

import json
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

_WASTE_TYPES = Literal[
    "crop_residue", "processing_waste", "packaging", "chemical_container",
    "organic_waste", "wastewater", "other",
]
_DISPOSAL_METHODS = Literal[
    "composting", "burning", "landfill", "recycling", "animal_feed",
    "biogas", "mulching", "other",
]
_COMPOST_FEEDSTOCK = Literal[
    "crop_residue", "manure", "food_waste", "green_waste", "mixed", "other",
]
_COMPOST_METHOD = Literal["heap", "pit", "vermiculture", "bokashi", "other"]
_CAPTURE_STATUS = Literal["recorded", "verified", "archived"]


class _WasteResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WasteAggregateByType(_WasteResponseModel):
    waste_type: _WASTE_TYPES
    total_kg: float
    record_count: int = Field(ge=1, strict=True)


class WasteAggregateByDisposalMethod(_WasteResponseModel):
    disposal_method: _DISPOSAL_METHODS | None
    total_kg: float
    record_count: int = Field(ge=1, strict=True)


class WastePeriodSummary(_WasteResponseModel):
    period_days: int = Field(ge=1, le=3650, strict=True)
    total_waste_kg: float
    total_records: int = Field(ge=0, strict=True)
    by_type: list[WasteAggregateByType] = Field(max_length=7)
    by_disposal_method: list[WasteAggregateByDisposalMethod] = Field(max_length=9)


class WasteStreamAggregate(_WasteResponseModel):
    waste_type: _WASTE_TYPES
    disposal_method: _DISPOSAL_METHODS | None
    quantity_unit: str | None
    record_count: int = Field(ge=1, strict=True)
    total_quantity: float
    first_date: str | None
    last_date: str | None


class CompostingAggregate(_WasteResponseModel):
    feedstock_type: _COMPOST_FEEDSTOCK
    compost_method: _COMPOST_METHOD
    record_count: int = Field(ge=1, strict=True)
    feedstock_kg: float
    total_output_kg: float
    weighted_yield_pct: float | None
    mean_batch_yield_pct: float | None
    mean_duration_days: float | None
    mean_temperature_c: float | None
    mean_moisture_pct: float | None
    graded_batches: int = Field(ge=0, strict=True)
    first_date: str | None
    last_date: str | None


class CompostingMethodAggregate(_WasteResponseModel):
    compost_method: _COMPOST_METHOD
    batches: int = Field(ge=1, strict=True)
    avg_yield_pct: float | None
    avg_feedstock_kg: float | None
    avg_output_kg: float | None
    avg_duration_days: float | None


class CompostQualityPoint(_WasteResponseModel):
    ph: float | None
    moisture_pct: float | None
    temperature_c: float | None
    output_yield_pct: float | None
    recorded_at: str


class CompostingEfficiencySummary(_WasteResponseModel):
    location_id: UUID
    total_batches: int = Field(ge=0, strict=True)
    total_feedstock_kg: float
    total_output_kg: float
    overall_yield_pct: float | None
    by_method: list[CompostingMethodAggregate] = Field(max_length=5)
    recent_quality: list[CompostQualityPoint] = Field(max_length=10)


class RecyclingAggregate(_WasteResponseModel):
    material_type: Literal["plastic", "metal", "glass", "paper", "organic", "other"]
    record_count: int = Field(ge=1, strict=True)
    quantity_kg: float
    first_date: str | None
    last_date: str | None


class PollutionIncidentAggregate(_WasteResponseModel):
    severity: Literal["low", "medium", "high", "critical"]
    status: Literal["open", "investigating", "remediation", "resolved", "closed"]
    record_count: int = Field(ge=1, strict=True)
    first_date: str | None
    last_date: str | None


class WasteSummaryResponse(_WasteResponseModel):
    location_id: UUID
    waste_summary: WastePeriodSummary
    waste_streams: list[WasteStreamAggregate]
    composting: list[CompostingAggregate] = Field(max_length=30)
    composting_efficiency: CompostingEfficiencySummary
    recycling: list[RecyclingAggregate] = Field(max_length=6)
    pollution_incidents: list[PollutionIncidentAggregate] = Field(max_length=20)


class PollutionIncidentReviewItem(_WasteResponseModel):
    incident_id: UUID
    incident_date: date
    incident_type: Literal[
        "chemical_spill", "runoff", "air_emission", "water_contamination",
        "waste_dumping", "other",
    ]
    severity: Literal["low", "medium", "high", "critical"]
    description: str = Field(max_length=2500)
    affected_area: str | None = Field(max_length=200)
    status: Literal["open", "investigating", "remediation"]


class PollutionIncidentReviewQueueResponse(_WasteResponseModel):
    location_id: UUID
    offset: int = Field(ge=0, le=1_000_000, strict=True)
    incidents: list[PollutionIncidentReviewItem] = Field(max_length=100)
    has_more: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_continuation(self):
        if self.has_more and (
            len(self.incidents) != 100 or self.offset + 100 > 1_000_000
        ):
            raise ValueError("Incident review continuation exceeds its page bounds")
        return self


class PollutionIncidentResolutionResponse(_WasteResponseModel):
    incident_id: UUID
    location_id: UUID
    resolution_date: date
    status: Literal["resolved"]
    replayed: bool


def register_waste_management_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.waste_management_incidents import (
        PollutionIncidentInvalid,
        create_location_pollution_incident,
        list_location_pollution_incidents,
        resolve_location_pollution_incident,
    )
    from services.gateway.waste_management_reads import get_location_waste_summary
    from services.gateway.waste_management_writes import (
        WasteManagementWriteInvalid,
        create_location_composting_record,
        create_location_recycling_record,
        create_location_waste_stream_record,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    async def bounded_payload(request: Request, *, max_bytes: int = 4096):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    return None, JSONResponse(
                        status_code=413,
                        content={"error": f"Waste request body exceeds {max_bytes // 1024} KB"},
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
            if len(body) > max_bytes:
                return None, JSONResponse(
                    status_code=413,
                    content={"error": f"Waste request body exceeds {max_bytes // 1024} KB"},
                    headers=headers,
                )
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Waste capture body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Waste capture body must be an object"},
                headers=headers,
            )
        return payload, None

    @router.get(
        "/operator/api/waste/{location_id}/summary",
        response_model=WasteSummaryResponse,
    )
    async def waste_summary(
        request: Request,
        location_id: str,
        days: str = "30",
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            period_days = int(days)
        except (TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "days must be an integer between 1 and 3650"},
                headers=headers,
            )
        if not 1 <= period_days <= 3650:
            return JSONResponse(
                status_code=400,
                content={"error": "days must be an integer between 1 and 3650"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_waste_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
                days=period_days,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Waste summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Waste summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = WasteSummaryResponse.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.composting_efficiency.location_id != UUID(location_id)
                or validated.waste_summary.period_days != period_days
            ):
                raise ValueError("Waste summary scope does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Waste summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Waste summary unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )

    @router.post("/operator/api/waste/{location_id}/records")
    async def create_waste_record(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_waste_stream_record,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified waste capture access is required"},
                headers=headers,
            )
        except WasteManagementWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location waste-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Waste capture input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Waste capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Waste capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/waste/{location_id}/composting")
    async def create_composting_record(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_composting_record,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified composting capture access is required"},
                headers=headers,
            )
        except WasteManagementWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location waste-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Composting input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Composting capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Composting capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/waste/{location_id}/recycling")
    async def create_recycling_record(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_recycling_record,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified recycling capture access is required"},
                headers=headers,
            )
        except WasteManagementWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location waste-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Recycling input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Recycling capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Recycling capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/waste/{location_id}/incidents")
    async def create_pollution_incident(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_payload(request, max_bytes=20 * 1024)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pollution_incident,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified incident capture access is required"},
                headers=headers,
            )
        except PollutionIncidentInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location waste-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Incident input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Incident capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Incident capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.get(
        "/operator/api/waste/{location_id}/incidents",
        response_model=PollutionIncidentReviewQueueResponse,
    )
    async def pollution_incident_review_queue(
        request: Request,
        location_id: str,
        offset: int = Query(default=0, ge=0, le=1_000_000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_pollution_incidents,
                request.state.operator_session.operator.operator_id,
                location_id,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified incident review access is required"},
                headers=headers,
            )
        except PollutionIncidentInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Incident review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Incident review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            queue = PollutionIncidentReviewQueueResponse.model_validate(result)
            if queue.location_id != UUID(location_id) or queue.offset != offset:
                raise ValueError("Incident queue scope does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Incident review queue response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Incident review queue unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(queue.model_dump(mode="json")), headers=headers
        )

    @router.post(
        "/operator/api/waste/{location_id}/incidents/{incident_id}/resolve",
        response_model=PollutionIncidentResolutionResponse,
    )
    async def resolve_pollution_incident(request: Request, location_id: str, incident_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                resolve_location_pollution_incident,
                request.state.operator_session.operator.operator_id,
                location_id,
                incident_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified incident review access is required"},
                headers=headers,
            )
        except PollutionIncidentInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location incident-review grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Incident resolution input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The incident is resolved or the request ID conflicts"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Incident resolution unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Incident resolution unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            resolution = PollutionIncidentResolutionResponse.model_validate(result)
            if (
                resolution.location_id != UUID(location_id)
                or resolution.incident_id != UUID(incident_id)
            ):
                raise ValueError("Incident resolution scope does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Incident resolution response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Incident resolution unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(resolution.model_dump(mode="json")),
            status_code=200,
            headers=headers,
        )
