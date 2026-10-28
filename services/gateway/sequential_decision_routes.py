"""OIDC routes for location-scoped sequential evidence summaries."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator


class _SequentialDecisionResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SequentialHypothesisStatusCounts(_SequentialDecisionResponseModel):
    draft: int = Field(ge=0, strict=True)
    active: int = Field(ge=0, strict=True)
    resolved: int = Field(ge=0, strict=True)
    retired: int = Field(ge=0, strict=True)


class SequentialEvidenceQualityCounts(_SequentialDecisionResponseModel):
    unverified: int = Field(ge=0, strict=True)
    provisional: int = Field(ge=0, strict=True)
    verified: int = Field(ge=0, strict=True)
    rejected: int = Field(ge=0, strict=True)
    stale: int = Field(ge=0, strict=True)


class SequentialDecisionActionCounts(_SequentialDecisionResponseModel):
    continue_: int = Field(ge=0, strict=True, alias="continue")
    act: int = Field(ge=0, strict=True)
    escalate: int = Field(ge=0, strict=True)
    stop: int = Field(ge=0, strict=True)
    reject: int = Field(ge=0, strict=True)
    insufficient_evidence: int = Field(ge=0, strict=True)


class SequentialDecisionSummary(_SequentialDecisionResponseModel):
    location_id: UUID
    hypothesis_count: int = Field(ge=0, strict=True)
    hypothesis_status_counts: SequentialHypothesisStatusCounts
    evidence_event_count: int = Field(ge=0, strict=True)
    evidence_quality_counts: SequentialEvidenceQualityCounts
    applied_evidence_event_count: int = Field(ge=0, strict=True)
    posterior_update_count: int = Field(ge=0, strict=True)
    latest_decision_action_counts: SequentialDecisionActionCounts


class SequentialEvidenceTimelineItem(_SequentialDecisionResponseModel):
    hypothesis_sequence: int = Field(ge=1, strict=True)
    subject_type: Literal["strategy_plan", "threat", "solution"]
    evidence_sequence: int = Field(ge=1, strict=True)
    observed_at: AwareDatetime
    ingested_at: AwareDatetime
    evidence_class: str = Field(min_length=1, max_length=40)
    quality_status: Literal["unverified", "provisional", "verified", "rejected", "stale"]
    posterior_update_sequence: int | None = Field(ge=1, strict=True)
    calculation_version: str | None = Field(max_length=40)
    posterior_updated_at: AwareDatetime | None


class SequentialEvidenceTimeline(_SequentialDecisionResponseModel):
    location_id: UUID
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    items: list[SequentialEvidenceTimelineItem] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10_000, strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.items) > self.limit:
            raise ValueError("page contains more items than requested")
        if self.has_more:
            if len(self.items) != self.limit:
                raise ValueError("has_more requires a full page")
            if self.offset + self.limit > 10_000:
                raise ValueError("has_more exceeds the supported offset boundary")
            if self.next_offset != self.offset + self.limit:
                raise ValueError("next_offset is inconsistent with the returned page")
        elif self.next_offset is not None:
            raise ValueError("next_offset must be empty when has_more is false")
        return self


def register_sequential_decision_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.sequential_decision_reads import (
        SequentialDecisionReadInvalid,
        SequentialDecisionResponseTooLarge,
        get_location_sequential_decision_summary,
        list_location_sequential_evidence_timeline,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def contracted_response(model, result, *, expected, failure):
        try:
            validated = model.model_validate(result)
            if any(getattr(validated, key) != value for key, value in expected.items()):
                raise ValueError("response does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.sequential_evidence").warning(
                "Sequential evidence response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=500, content={"error": failure}, headers=headers)
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json", by_alias=True)),
            headers=headers,
        )

    @router.get(
        "/operator/api/sequential-evidence/{location_id}/summary",
        response_model=SequentialDecisionSummary,
    )
    async def location_sequential_decision_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_sequential_decision_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified sequential evidence access is required"},
                headers=headers,
            )
        except SequentialDecisionReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location sequential evidence read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.sequential_evidence").warning(
                "Sequential evidence summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Sequential evidence summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            SequentialDecisionSummary,
            result,
            expected={"location_id": UUID(location_id)},
            failure="Sequential evidence summary unavailable",
        )

    @router.get(
        "/operator/api/sequential-evidence/{location_id}/events",
        response_model=SequentialEvidenceTimeline,
    )
    async def location_sequential_evidence_timeline(
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
                list_location_sequential_evidence_timeline,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified sequential evidence access is required"},
                headers=headers,
            )
        except SequentialDecisionReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SequentialDecisionResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location sequential evidence read grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "22023":
                return JSONResponse(status_code=400, content={"error": "Sequential evidence page is invalid"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.sequential_evidence").warning(
                "Sequential evidence timeline unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Sequential evidence timeline unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            SequentialEvidenceTimeline,
            result,
            expected={
                "location_id": UUID(location_id),
                "limit": limit,
                "offset": offset,
            },
            failure="Sequential evidence timeline unavailable",
        )
