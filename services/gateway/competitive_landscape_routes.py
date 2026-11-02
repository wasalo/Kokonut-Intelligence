"""OIDC routes for location-scoped competitive landscape summaries."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from services.gateway.competitive_landscape_reads import MAX_COMPETITIVE_LANDSCAPE_OFFSET


class _CompetitiveLandscapeResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CompetitiveLandscapeSummary(_CompetitiveLandscapeResponseModel):
    landscape_id: UUID
    strategy_plan_id: UUID
    industry: str | None = Field(max_length=160)
    geography: str | None = Field(max_length=160)
    period_start: date
    period_end: date
    landscape_status: Literal["draft", "submitted", "verified", "published", "retired"]
    confidence: Literal["high", "moderate", "low", "insufficient_evidence"] | None
    updated_at: AwareDatetime
    actor_count: int = Field(ge=0, strict=True)
    high_or_critical_actor_count: int = Field(ge=0, strict=True)
    force_observation_count: int = Field(ge=0, strict=True)
    average_force_pressure: float | None = Field(default=None, ge=0, le=100)
    worsening_force_count: int = Field(ge=0, strict=True)
    signal_count: int = Field(ge=0, strict=True)
    unreviewed_critical_signal_count: int = Field(ge=0, strict=True)
    verified_advantage_count: int = Field(ge=0, strict=True)
    average_verified_defensibility: float | None
    verified_advantage_outcome_count: int = Field(ge=0, strict=True)
    latest_verified_outcome_period_end: date | None

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("competitive landscape period end precedes start")
        if self.high_or_critical_actor_count > self.actor_count:
            raise ValueError("competitive landscape actor counts are inconsistent")
        if self.unreviewed_critical_signal_count > self.signal_count:
            raise ValueError("competitive landscape signal counts are inconsistent")
        return self


class CompetitiveLandscapeSummaryPage(_CompetitiveLandscapeResponseModel):
    location_id: UUID
    offset: int = Field(ge=0, le=MAX_COMPETITIVE_LANDSCAPE_OFFSET, strict=True)
    landscapes: list[CompetitiveLandscapeSummary] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(
        default=None, ge=0, le=MAX_COMPETITIVE_LANDSCAPE_OFFSET, strict=True
    )

    @model_validator(mode="after")
    def validate_pagination(self):
        if self.has_more != (self.next_offset is not None):
            raise ValueError("has_more and next_offset are inconsistent")
        return self


def register_competitive_landscape_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.competitive_landscape_reads import (
        CompetitiveLandscapeReadInvalid,
        list_location_competitive_landscape_summaries,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/competitive-landscape/{location_id}/summaries",
        response_model=CompetitiveLandscapeSummaryPage,
    )
    async def location_competitive_landscape_summaries(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=MAX_COMPETITIVE_LANDSCAPE_OFFSET),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_competitive_landscape_summaries,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified competitive landscape access is required"},
                headers=headers,
            )
        except CompetitiveLandscapeReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location competitive landscape read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.competitive_landscape").warning(
                "Competitive landscape read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Competitive landscape read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = CompetitiveLandscapeSummaryPage.model_validate(result)
            expected_location = UUID(location_id)
            expected_next_offset = offset + limit if validated.has_more else None
            if (
                validated.location_id != expected_location
                or validated.offset != offset
                or validated.next_offset != expected_next_offset
                or len(validated.landscapes) > limit
            ):
                raise ValueError("Competitive landscape response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.competitive_landscape").warning(
                "Competitive landscape response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Competitive landscape read unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
