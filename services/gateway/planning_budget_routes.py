"""OIDC routes for location-scoped planning budget summaries."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class _PlanningBudgetResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PlanningBudgetSummary(_PlanningBudgetResponseModel):
    financial_plan_id: UUID
    plan_status: Literal["draft", "approved", "active", "closed", "cancelled"]
    currency: str = Field(min_length=1, max_length=10)
    period_start: date
    period_end: date
    has_objective: bool = Field(strict=True)
    budget_line_count: int = Field(ge=1, strict=True)
    planned_amount: float
    verified_expense_amount: float
    budget_variance: float
    nonmatching_currency_expense_count: int = Field(ge=0, strict=True)
    planning_scenario_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("planning period end precedes start")
        return self


class PlanningBudgetSummaryPage(_PlanningBudgetResponseModel):
    location_id: UUID
    offset: int = Field(ge=0, le=10_000, strict=True)
    plans: list[PlanningBudgetSummary] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(default=None, ge=0, le=10_000, strict=True)

    @model_validator(mode="after")
    def validate_continuation(self):
        if self.has_more != (self.next_offset is not None):
            raise ValueError("has_more and next_offset are inconsistent")
        return self


def register_planning_budget_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.planning_budget_reads import (
        PlanningBudgetReadInvalid,
        list_location_budget_summaries,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/planning/{location_id}/budgets",
        response_model=PlanningBudgetSummaryPage,
    )
    async def location_planning_budgets(
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
                list_location_budget_summaries,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified planning access is required"},
                headers=headers,
            )
        except PlanningBudgetReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location planning budget read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.planning_budget").warning(
                "Planning budget read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Planning budget read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = PlanningBudgetSummaryPage.model_validate(result)
            expected_next_offset = offset + limit if validated.has_more else None
            if (
                validated.location_id != UUID(location_id)
                or validated.offset != offset
                or len(validated.plans) > limit
                or (validated.has_more and expected_next_offset > 10_000)
                or validated.next_offset != expected_next_offset
            ):
                raise ValueError("Planning budget response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.planning_budget").warning(
                "Planning budget response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Planning budget read unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
