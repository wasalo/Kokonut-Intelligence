"""OIDC routes for location-scoped human review of AI summary drafts."""

import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, model_validator

_SOURCE_TABLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


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
ReviewBlocker = Literal[
    "empty_content",
    "missing_source_lineage",
    "content_exceeds_review_limit",
    "creator_unattributed",
    "self_review",
    "worker_task_unregistered",
]
CreatorKind = Literal[
    "unregistered_worker",
    "operator_task",
    "registered_worker",
    "operator",
    "unattributed",
]


class _StrictResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AiSummarySourceReference(_StrictResponseModel):
    record_ids: list[StrictUuid] = Field(max_length=50)
    row_count: int = Field(ge=0, le=9_223_372_036_854_775_807)
    truncated: bool
    scope: Literal["location", "network", "location_or_network"] | None = None

    @model_validator(mode="after")
    def validate_counts(self):
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValueError("Source-reference IDs must be unique")
        if self.row_count < len(self.record_ids):
            raise ValueError("Source-reference row count is smaller than its sample")
        if self.truncated != (self.row_count > len(self.record_ids)):
            raise ValueError("Source-reference truncation flag is inconsistent")
        return self


class AiSummaryReviewItem(_StrictResponseModel):
    summary_id: StrictUuid
    summary_type: str | None = Field(
        default=None, max_length=100, pattern=r"^[a-z][a-z0-9_]{0,99}$"
    )
    content: str = Field(max_length=20_000)
    content_truncated: bool
    source_tables: list[str] = Field(max_length=20)
    source_references: dict[str, AiSummarySourceReference] = Field(
        max_length=10,
        json_schema_extra={
            "propertyNames": {"pattern": _SOURCE_TABLE_PATTERN.pattern}
        },
    )
    model_version: str | None = Field(default=None, max_length=100)
    created_at: AwareDatetime | None
    review_ready: bool
    blocked_reasons: list[ReviewBlocker] = Field(max_length=5)
    creator_task_key: str | None = Field(
        default=None, max_length=100, pattern=r"^[a-z][a-z0-9_]{0,99}$"
    )
    creator_run_id: StrictUuid | None
    creator_kind: CreatorKind
    creator_operator_id: StrictUuid | None
    creator_request_id: StrictUuid | None

    @model_validator(mode="after")
    def validate_source_tables(self):
        if any(_SOURCE_TABLE_PATTERN.fullmatch(table) is None for table in self.source_tables):
            raise ValueError("Source-table names are invalid")
        if len(set(self.source_tables)) != len(self.source_tables):
            raise ValueError("Source-table names must be unique")
        if any(
            _SOURCE_TABLE_PATTERN.fullmatch(table) is None
            for table in self.source_references
        ):
            raise ValueError("Source-reference table names are invalid")
        if not set(self.source_references).issubset(self.source_tables):
            raise ValueError("Source references must match declared source tables")
        if self.review_ready != (not self.blocked_reasons):
            raise ValueError("Review readiness must match the blocker list")
        return self


class AiSummaryReviewPage(_StrictResponseModel):
    location_id: StrictUuid
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=10_000)
    summaries: list[AiSummaryReviewItem] = Field(max_length=50)
    has_more: bool

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.summaries) > self.limit:
            raise ValueError("Review page exceeds its requested limit")
        if self.has_more and (
            len(self.summaries) != self.limit or self.offset + self.limit > 10_000
        ):
            raise ValueError("Review page continuation is inconsistent")
        return self


class AiSummaryReviewError(_StrictResponseModel):
    error: str


def register_ai_summary_review_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.ai_summary_review import (
        AiSummaryReviewInvalid,
        decide_location_ai_summary_review,
        list_location_ai_summary_reviews,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
    documented_error_headers = {
        "Cache-Control": {
            "description": "Private review responses are never cached.",
            "schema": {"type": "string", "example": "no-store"},
        },
        "Vary": {
            "description": "Response varies by the operator session cookie.",
            "schema": {"type": "string", "example": "Cookie"},
        },
    }
    error_responses = {
        status: {
            "model": AiSummaryReviewError,
            "description": description,
            "headers": documented_error_headers,
        }
        for status, description in {
            400: "The review request is invalid.",
            403: "The operator lacks a current tenant-qualified review grant.",
            404: "Operator OIDC is disabled.",
            409: "The summary cannot accept this review decision.",
            500: "The private review projection failed its response contract.",
            503: "The review store is temporarily unavailable.",
        }.items()
    }

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location AI-summary review grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "The AI summary is not currently reviewable"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "AI-summary review request is invalid"},
                headers=headers,
            )
        if code == "23505":
            return JSONResponse(
                status_code=409,
                content={"error": "The AI summary already has a review decision"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.ai_summary_review").warning(
            "AI summary review unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "AI summary review unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.get(
        "/operator/api/ai-summaries/{location_id}/reviews",
        response_model=AiSummaryReviewPage,
        responses=error_responses,
    )
    async def list_summary_reviews(
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
                list_location_ai_summary_reviews,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified AI-summary review access is required"},
                headers=headers,
            )
        except AiSummaryReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        try:
            page = AiSummaryReviewPage.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Review page identity does not match the request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.ai_summary_review").warning(
                "AI summary review projection violates its response contract (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "AI summary review unavailable"},
                headers=headers,
            )
        return JSONResponse(page.model_dump(mode="json"), headers=headers)

    @router.post(
        "/operator/api/ai-summaries/{location_id}/reviews/{summary_id}/decision"
    )
    async def decide_summary_review(
        request: Request,
        location_id: str,
        summary_id: str,
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {
            "decision",
            "request_id",
            "reason_code",
        }:
            return JSONResponse(
                status_code=400,
                content={"error": "Body must contain decision, request_id, and reason_code only"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                decide_location_ai_summary_review,
                request.state.operator_session.operator.operator_id,
                location_id,
                summary_id,
                decision=payload["decision"],
                request_id=payload["request_id"],
                reason_code=payload["reason_code"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified AI-summary review access is required"},
                headers=headers,
            )
        except AiSummaryReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
