"""OIDC routes for location-scoped business architecture summaries."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _BusinessArchitectureResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BusinessArchitectureMissionResponse(_BusinessArchitectureResponseModel):
    statement_type: Literal["vision", "mission", "values"]
    statement_text: str
    effective_date: date | None
    review_date: date | None


class BusinessArchitectureMappingResponse(_BusinessArchitectureResponseModel):
    roadmap_id: UUID
    roadmap_name: str
    roadmap_status: Literal["approved", "active", "reviewed"]
    planning_horizon_start: date | None
    planning_horizon_end: date | None
    requirement_id: UUID | None
    requirement_title: str | None
    need_type: Literal[
        "business", "customer", "operational", "regulatory", "sustainability"
    ] | None
    priority: int | None = Field(default=None, ge=1, le=5, strict=True)
    requirement_status: Literal[
        "proposed", "validated", "in_progress", "met", "deferred"
    ] | None
    capability_name: str | None
    value_stream_name: str | None
    strategy_perspective: Literal[
        "financial", "customer", "internal_process", "learning_growth"
    ] | None


class BusinessArchitectureSummaryResponse(_BusinessArchitectureResponseModel):
    location_id: UUID
    offset: int = Field(ge=0, le=10000, strict=True)
    missions: list[BusinessArchitectureMissionResponse] = Field(max_length=3)
    mappings: list[BusinessArchitectureMappingResponse] = Field(max_length=50)
    has_more: bool
    next_offset: int | None = Field(default=None, ge=0, le=10050, strict=True)


def register_business_architecture_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.business_architecture_reads import (
        BusinessArchitectureReadInvalid,
        get_location_business_architecture_summary,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/business-architecture/{location_id}/summary",
        response_model=BusinessArchitectureSummaryResponse,
    )
    async def location_business_architecture_summary(
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
                get_location_business_architecture_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified business architecture access is required"},
                headers=headers,
            )
        except BusinessArchitectureReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location business architecture read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.business_architecture").warning(
                "Business architecture read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Business architecture read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = BusinessArchitectureSummaryResponse.model_validate(
                jsonable_encoder(result)
            )
            if validated.location_id != UUID(location_id):
                raise ValueError("Business architecture location does not match request")
            if validated.offset != offset:
                raise ValueError("Business architecture page does not match request")
            expected_next_offset = offset + limit if validated.has_more else None
            if validated.next_offset != expected_next_offset:
                raise ValueError("Business architecture continuation does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.business_architecture").warning(
                "Business architecture response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Business architecture read unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
