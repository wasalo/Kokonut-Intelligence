"""OIDC routes for location-scoped business model canvas reads."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator


class _BusinessCanvasResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BusinessCanvasContentResponse(_BusinessCanvasResponseModel):
    key_partners: JsonValue
    key_activities: JsonValue
    key_resources: JsonValue
    value_propositions: JsonValue
    customer_relationships: JsonValue
    channels: JsonValue
    customer_segments: JsonValue
    revenue_streams: JsonValue
    cost_structure: JsonValue


class BusinessCanvasSummaryResponse(_BusinessCanvasResponseModel):
    canvas_id: UUID
    canvas_name: str | None = Field(default=None, max_length=255)
    canvas_description: str | None
    lifecycle_status: Literal["draft", "submitted", "verified", "published", "rejected"]
    fiscal_year: int | None = Field(default=None, strict=True)
    schema_version: str | None = Field(default=None, max_length=50)
    version: int | None = Field(default=None, ge=1, strict=True)
    health_score: float | None = Field(default=None, ge=0, le=100)
    tags: list[str] | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    content: BusinessCanvasContentResponse
    source_system: str | None = Field(default=None, max_length=100)
    source_reference: str | None = Field(default=None, max_length=255)


class BusinessCanvasListResponse(_BusinessCanvasResponseModel):
    location_id: UUID
    offset: int = Field(ge=0, le=10_000, strict=True)
    canvases: list[BusinessCanvasSummaryResponse] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(default=None, ge=0, le=10_000, strict=True)

    @model_validator(mode="after")
    def validate_continuation(self):
        if self.has_more != (self.next_offset is not None):
            raise ValueError("has_more and next_offset are inconsistent")
        return self


class BusinessCanvasDraftCreateResponse(_BusinessCanvasResponseModel):
    location_id: UUID
    canvas_id: UUID
    status: Literal["draft"]
    version: int = Field(ge=1, strict=True)
    created_at: AwareDatetime
    replayed: bool = Field(strict=True)


class BusinessCanvasGeneratedDraftCreateResponse(BusinessCanvasDraftCreateResponse):
    generated_from: list[
        Literal[
            "location_cooperative/supply_agreement",
            "verified_farm_activity",
            "location_sensor/energy/shared_asset",
            "verified_impact_claim",
            "location_content_delivery",
            "verified_buyer_segment",
            "verified_revenue_event_usd",
            "verified_expense_event_by_currency",
            "consented_public_feedback_cohort",
        ]
    ] = Field(max_length=9)
    populated_blocks: list[
        Literal[
            "key_partners",
            "key_activities",
            "key_resources",
            "value_propositions",
            "customer_relationships",
            "channels",
            "customer_segments",
            "revenue_streams",
            "cost_structure",
        ]
    ] = Field(max_length=9)

    @model_validator(mode="after")
    def validate_unique_provenance(self):
        if len(set(self.generated_from)) != len(self.generated_from):
            raise ValueError("generated_from must not contain duplicates")
        if len(set(self.populated_blocks)) != len(self.populated_blocks):
            raise ValueError("populated_blocks must not contain duplicates")
        return self


def register_business_planning_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.business_planning_reads import (
        BusinessPlanningReadInvalid,
        list_location_business_model_canvases,
    )
    from services.gateway.business_planning_writes import (
        BusinessPlanningWriteInvalid,
        create_location_business_model_canvas,
        create_location_business_model_canvas_from_data,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/business-planning/{location_id}/canvases",
        response_model=BusinessCanvasListResponse,
    )
    async def location_business_model_canvases(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_business_model_canvases,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified business planning access is required"},
                headers=headers,
            )
        except BusinessPlanningReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location business planning read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.business_planning").warning(
                "Business planning read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Business planning read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = BusinessCanvasListResponse.model_validate(result)
            expected_location = UUID(location_id)
            expected_next_offset = offset + limit if validated.has_more else None
            if (
                validated.location_id != expected_location
                or validated.offset != offset
                or validated.next_offset != expected_next_offset
                or len(validated.canvases) > limit
            ):
                raise ValueError("Business canvas response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.business_planning").warning(
                "Business planning response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Business planning read unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )

    async def _create_canvas_response(request, location_id, writer, response_model):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "A business canvas JSON object is required"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "A business canvas JSON object is required"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                writer,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified business planning access is required"},
                headers=headers,
            )
        except BusinessPlanningWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location business planning create grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Business canvas draft fields are invalid"},
                    headers=headers,
                )
            if code in {"23505", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Business canvas request conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.business_planning").warning(
                "Business canvas creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Business canvas creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = response_model.model_validate(result)
            if validated.location_id != UUID(location_id):
                raise ValueError("Business canvas response location does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.business_planning").warning(
                "Business canvas creation response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Business canvas creation unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            status_code=200 if validated.replayed else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/business-planning/{location_id}/canvases",
        response_model=BusinessCanvasDraftCreateResponse,
        status_code=201,
        responses={200: {"model": BusinessCanvasDraftCreateResponse}},
    )
    async def create_location_business_model_canvas_draft(
        request: Request,
        location_id: str,
    ):
        return await _create_canvas_response(
            request,
            location_id,
            create_location_business_model_canvas,
            BusinessCanvasDraftCreateResponse,
        )

    @router.post(
        "/operator/api/business-planning/{location_id}/canvases/from-data",
        response_model=BusinessCanvasGeneratedDraftCreateResponse,
        status_code=201,
        responses={200: {"model": BusinessCanvasGeneratedDraftCreateResponse}},
    )
    async def create_location_business_model_canvas_from_data_draft(
        request: Request,
        location_id: str,
    ):
        return await _create_canvas_response(
            request,
            location_id,
            create_location_business_model_canvas_from_data,
            BusinessCanvasGeneratedDraftCreateResponse,
        )
