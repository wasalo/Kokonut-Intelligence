"""OIDC routes for location-scoped coordination governance summaries."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CoordinationGovernanceSummaryResponse(BaseModel):
    """Aggregate-only response returned by migration 458's scoped function."""

    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    alliance_count: int = Field(ge=0, strict=True)
    draft_alliance_count: int = Field(ge=0, strict=True)
    proposed_alliance_count: int = Field(ge=0, strict=True)
    approved_alliance_count: int = Field(ge=0, strict=True)
    active_alliance_count: int = Field(ge=0, strict=True)
    paused_alliance_count: int = Field(ge=0, strict=True)
    completed_alliance_count: int = Field(ge=0, strict=True)
    dissolved_alliance_count: int = Field(ge=0, strict=True)
    rejected_alliance_count: int = Field(ge=0, strict=True)
    overdue_review_count: int = Field(ge=0, strict=True)
    open_conflict_declaration_count: int = Field(ge=0, strict=True)
    unreviewed_harm_analysis_count: int = Field(ge=0, strict=True)
    open_appeal_count: int = Field(ge=0, strict=True)
    open_remedy_count: int = Field(ge=0, strict=True)
    preserved_minority_view_count: int = Field(ge=0, strict=True)
    completed_knowledge_exchange_count: int = Field(ge=0, strict=True)
    open_learning_link_count: int = Field(ge=0, strict=True)
    draft_metric_observation_count: int = Field(ge=0, strict=True)
    rejected_metric_observation_count: int = Field(ge=0, strict=True)


def register_coordination_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.coordination_reads import (
        CoordinationReadInvalid,
        get_location_coordination_governance_summary,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/coordination/{location_id}/summary",
        response_model=CoordinationGovernanceSummaryResponse,
    )
    async def location_coordination_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_coordination_governance_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified coordination access is required"},
                headers=headers,
            )
        except CoordinationReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location coordination read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.coordination").warning(
                "Coordination summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Coordination summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = CoordinationGovernanceSummaryResponse.model_validate(result)
        except ValidationError as exc:
            from services.common.logging import get_logger

            get_logger("gateway.coordination").warning(
                "Coordination summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Coordination summary unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers=headers,
        )
