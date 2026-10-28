"""OIDC routes for location-scoped management workload summaries."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError


class ManagementWorkSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    location_id: UUID
    work_item_count: int = Field(ge=0, strict=True)
    open_work_item_count: int = Field(ge=0, strict=True)
    draft_count: int = Field(ge=0, strict=True)
    assigned_count: int = Field(ge=0, strict=True)
    in_progress_count: int = Field(ge=0, strict=True)
    blocked_count: int = Field(ge=0, strict=True)
    done_count: int = Field(ge=0, strict=True)
    cancelled_count: int = Field(ge=0, strict=True)
    high_priority_open_count: int = Field(ge=0, strict=True)
    critical_priority_open_count: int = Field(ge=0, strict=True)
    overdue_count: int = Field(ge=0, strict=True)
    sla_breached_count: int = Field(ge=0, strict=True)
    pending_claim_count: int = Field(ge=0, strict=True)
    accepted_claim_count: int = Field(ge=0, strict=True)
    open_escalation_count: int = Field(ge=0, strict=True)
    resolved_escalation_count: int = Field(ge=0, strict=True)
    latest_work_event_at: AwareDatetime | None


def register_management_work_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.management_work_reads import (
        ManagementWorkReadInvalid,
        location_management_work_summary,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/management/{location_id}/summary",
        response_model=ManagementWorkSummaryResponse,
    )
    async def management_work_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                location_management_work_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified management access is required"},
                headers=headers,
            )
        except ManagementWorkReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location management read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.management_work").warning(
                "Management work summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Management work summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = ManagementWorkSummaryResponse.model_validate(result)
            if validated.location_id != UUID(location_id):
                raise ValueError("Management response location does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.management_work").warning(
                "Management work summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Management work summary unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
