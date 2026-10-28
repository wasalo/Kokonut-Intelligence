"""OIDC routes for the location-scoped strategy plan projection."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from services.gateway.strategy_reads import MAX_STRATEGY_OFFSET, MAX_STRATEGY_PAGE_SIZE


class _StrategyResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StrategyPlanSummary(_StrategyResponseModel):
    strategy_plan_id: UUID
    plan_name: str = Field(max_length=255)
    version: int = Field(gt=0, strict=True)
    plan_status: Literal["draft", "submitted", "approved", "active", "superseded", "retired"]
    visibility: Literal["private", "limited", "public"]
    planning_horizon_start: date
    planning_horizon_end: date
    updated_at: AwareDatetime
    cascade_mode: Literal["inherited", "adapted", "independent"]
    cascade_status: Literal["not_applicable", "aligned", "needs_review", "conflicted"]
    has_parent_strategy: bool = Field(strict=True)
    objective_count: int = Field(ge=0, strict=True)
    initiative_count: int = Field(ge=0, strict=True)
    completed_initiative_count: int = Field(ge=0, strict=True)
    investment_case_count: int = Field(ge=0, strict=True)
    recommended_investment_count: int = Field(ge=0, strict=True)
    open_coherence_finding_count: int = Field(ge=0, strict=True)
    blocking_finding_count: int = Field(ge=0, strict=True)
    structural_gate_status: Literal["ready", "blocked"]
    open_review_task_count: int = Field(ge=0, strict=True)
    submitted_allocation_count: int = Field(ge=0, strict=True)
    approved_allocation_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_planning_horizon(self):
        if self.planning_horizon_end < self.planning_horizon_start:
            raise ValueError("planning horizon end precedes its start")
        return self


class StrategyPlanListResponse(_StrategyResponseModel):
    location_id: UUID
    offset: int = Field(ge=0, le=MAX_STRATEGY_OFFSET, strict=True)
    plans: list[StrategyPlanSummary] = Field(max_length=MAX_STRATEGY_PAGE_SIZE)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(
        default=None, ge=0, le=MAX_STRATEGY_OFFSET, strict=True
    )

    @model_validator(mode="after")
    def validate_pagination(self):
        if self.has_more != (self.next_offset is not None):
            raise ValueError("has_more and next_offset are inconsistent")
        return self


def register_strategy_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.strategy_reads import (
        StrategyReadInvalid,
        list_location_strategy_plan_summaries,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/strategy/{location_id}/plans",
        response_model=StrategyPlanListResponse,
    )
    async def location_strategy_plans(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=MAX_STRATEGY_PAGE_SIZE),
        offset: int = Query(default=0, ge=0, le=MAX_STRATEGY_OFFSET),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_strategy_plan_summaries,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified strategy access is required"},
                headers=headers,
            )
        except StrategyReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location strategy read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.strategy").warning(
                "Strategy plan read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Strategy plan read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = StrategyPlanListResponse.model_validate(result)
            expected_offset = UUID(location_id)
            expected_next_offset = offset + limit if validated.has_more else None
            if (
                validated.location_id != expected_offset
                or validated.offset != offset
                or validated.next_offset != expected_next_offset
                or len(validated.plans) > limit
            ):
                raise ValueError("Strategy response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.strategy").warning(
                "Strategy plan response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Strategy plan read unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers=headers,
        )
