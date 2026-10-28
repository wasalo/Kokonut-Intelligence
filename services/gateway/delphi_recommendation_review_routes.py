"""OIDC routes for location-scoped human review of Delphi drafts."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, ValidationError


def _strict_uuid(value):
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise ValueError("UUID values must be strings")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("UUID value is invalid") from exc


StrictUuid = Annotated[UUID, BeforeValidator(_strict_uuid)]
DelphiRecommendationBlocker = Literal[
    "self_review",
    "diversity_assessment_required",
    "minority_report_review_required",
]


class _RecommendationReviewResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class DelphiRecommendationReviewItem(_RecommendationReviewResponseModel):
    recommendation_id: StrictUuid
    study_id: StrictUuid
    study_title: str = Field(max_length=255)
    study_status: Literal["draft", "open", "closed"]
    summary: str | None = Field(max_length=4000)
    recommendation_text: str = Field(min_length=1, max_length=20_000)
    created_at: AwareDatetime | None
    review_ready: bool
    blocked_reasons: list[DelphiRecommendationBlocker] = Field(max_length=3)

    def validate_review_state(self):
        if self.review_ready != (not self.blocked_reasons):
            raise ValueError("review readiness does not match its blockers")
        return self


class DelphiRecommendationReviewPage(_RecommendationReviewResponseModel):
    location_id: StrictUuid
    offset: int = Field(ge=0, le=10_000)
    recommendations: list[DelphiRecommendationReviewItem] = Field(max_length=50)
    has_more: bool

    def validate_request(self, *, location_id: UUID, limit: int, offset: int):
        if self.location_id != location_id or self.offset != offset:
            raise ValueError("response scope does not match request")
        if len(self.recommendations) > limit:
            raise ValueError("response exceeds requested page size")
        if self.has_more and (
            len(self.recommendations) != limit or offset + limit > 10_000
        ):
            raise ValueError("response continuation exceeds requested bounds")
        for recommendation in self.recommendations:
            recommendation.validate_review_state()
        return self


def register_delphi_recommendation_review_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_recommendation_review import (
        DelphiReviewInvalid,
        decide_location_delphi_recommendation,
        list_location_delphi_recommendation_reviews,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location Delphi review grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "The recommendation is not currently reviewable"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi review request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_recommendation_review").warning(
            "Delphi recommendation review unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi recommendation review unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.get(
        "/operator/api/delphi/{location_id}/recommendations",
        response_model=DelphiRecommendationReviewPage,
    )
    async def list_recommendation_reviews(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=50),
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
                list_location_delphi_recommendation_reviews,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi review access is required"},
                headers=headers,
            )
        except DelphiReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        try:
            page = DelphiRecommendationReviewPage.model_validate(result)
            page.validate_request(
                location_id=UUID(location_id), limit=limit, offset=offset
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_recommendation_review").warning(
                "Delphi recommendation response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi recommendation review unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="json")), headers=headers
        )

    @router.post(
        "/operator/api/delphi/{location_id}/recommendations/{recommendation_id}/decision"
    )
    async def decide_recommendation_review(
        request: Request,
        location_id: str,
        recommendation_id: str,
    ):
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
                content={"error": "A JSON decision object is required"},
                headers=headers,
            )
        if (
            not isinstance(payload, dict)
            or set(payload) != {"decision", "request_id", "reason_code"}
            or not all(isinstance(payload.get(key), str) for key in payload)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Decision fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                decide_location_delphi_recommendation,
                request.state.operator_session.operator.operator_id,
                location_id,
                recommendation_id,
                decision=payload["decision"],
                request_id=payload["request_id"],
                reason_code=payload["reason_code"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi review access is required"},
                headers=headers,
            )
        except DelphiReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
