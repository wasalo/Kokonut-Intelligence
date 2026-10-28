"""OIDC routes for location-scoped stakeholder identity review."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator


class _IdentityResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class IdentityReviewCase(_IdentityResponseModel):
    case_id: UUID
    candidate_party_id: UUID | None
    candidate_name: str | None = Field(max_length=255)
    source_label: str | None = Field(max_length=301)
    match_method: Literal["manual", "exact_identifier", "verified_document", "community_review"]
    evidence_code: Literal[
        "verified_identifier", "document_review", "participant_confirmation", "community_review"
    ]
    confidence: Decimal = Field(ge=0, le=1, max_digits=5, decimal_places=4)
    created_at: AwareDatetime


class IdentityReviewCursor(_IdentityResponseModel):
    created_at: AwareDatetime
    case_id: UUID


class IdentityReviewPage(_IdentityResponseModel):
    location_id: UUID
    items: list[IdentityReviewCase] = Field(max_length=50)
    next_cursor: IdentityReviewCursor | None

    @model_validator(mode="after")
    def validate_cursor_matches_page(self):
        if self.next_cursor is not None:
            if not self.items:
                raise ValueError("a continuation cursor requires a nonempty page")
            last = self.items[-1]
            if (
                self.next_cursor.created_at != last.created_at
                or self.next_cursor.case_id != last.case_id
            ):
                raise ValueError("continuation cursor must identify the last item")
        return self


class IdentityReviewError(_IdentityResponseModel):
    error: str


def _identity_page_matches_request(page, *, location_id, limit, cursor_created_at, cursor_case_id):
    if (
        page.location_id != UUID(location_id)
        or len(page.items) > limit
        or (cursor_created_at is None) != (cursor_case_id is None)
    ):
        return False
    if page.next_cursor is not None and len(page.items) != limit:
        return False
    keys = [(item.created_at, item.case_id) for item in page.items]
    if any(left <= right for left, right in zip(keys, keys[1:])):
        return False
    if cursor_created_at is not None and cursor_case_id is not None:
        cursor_time = datetime.fromisoformat(cursor_created_at.replace("Z", "+00:00"))
        cursor_key = (cursor_time, UUID(cursor_case_id))
        if any(key >= cursor_key for key in keys):
            return False
    return True


def register_stakeholder_identity_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.stakeholder_identity import (
        StakeholderIdentityInvalid,
        decide_location_party_identity,
        list_location_party_identity_cases,
        propose_location_party_identity,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def operator_disabled():
        return JSONResponse(
            status_code=404,
            content={"error": "Operator OIDC is disabled"},
            headers=headers,
        )

    def failure(exc):
        if isinstance(exc, (TenantContextDenied, psycopg2.errors.InsufficientPrivilege)):
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified identity access is required"},
                headers=headers,
            )
        if isinstance(exc, StakeholderIdentityInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, psycopg2.Error):
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location identity grant and consent are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Identity request is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Identity case not found"}, headers=headers)
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(status_code=409, content={"error": "Identity case conflicts with current state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.stakeholder_identity").warning(
                "Stakeholder identity request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Stakeholder identity service unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        raise exc

    review_error_responses = {
        status: {"model": IdentityReviewError, "description": description}
        for status, description in {
            400: "The identity review cursor is invalid.",
            403: "The operator lacks current location-scoped identity review access.",
            404: "Operator OIDC is disabled.",
            500: "The identity review projection failed its response contract.",
            503: "The identity review service is unavailable.",
        }.items()
    }

    @router.get(
        "/operator/api/stakeholder-identity/{location_id}/cases",
        response_model=IdentityReviewPage,
        responses=review_error_responses,
    )
    async def identity_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=50),
        cursor_created_at: str | None = None,
        cursor_case_id: str | None = None,
    ):
        if provider is None:
            return operator_disabled()
        try:
            result = await run_in_threadpool(
                list_location_party_identity_cases,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_case_id=cursor_case_id,
            )
        except Exception as exc:
            return failure(exc)
        try:
            page = IdentityReviewPage.model_validate(result)
            if not _identity_page_matches_request(
                page,
                location_id=location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_case_id=cursor_case_id,
            ):
                raise ValueError("identity review page does not match request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.stakeholder_identity").warning(
                "Identity review response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Identity review queue unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="python")),
            headers=headers,
        )

    @router.post("/operator/api/stakeholder-identity/{location_id}/cases", status_code=201)
    async def create_identity_case(request: Request, location_id: str):
        if provider is None:
            return operator_disabled()
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        allowed = {
            "source_profile_id", "candidate_party_id", "request_id", "match_method",
            "evidence_code", "confidence",
        }
        if not isinstance(payload, dict) or set(payload) != allowed:
            return JSONResponse(
                status_code=400,
                content={"error": "Identity proposal must contain only the supported structured fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_party_identity,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload["source_profile_id"],
                payload["candidate_party_id"],
                payload["request_id"],
                payload["match_method"],
                payload["evidence_code"],
                payload["confidence"],
            )
        except Exception as exc:
            return failure(exc)
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.post(
        "/operator/api/stakeholder-identity/{location_id}/cases/{case_id}/decision"
    )
    async def decide_identity_case(request: Request, location_id: str, case_id: str):
        if provider is None:
            return operator_disabled()
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "decision", "reason_code"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Identity decision must contain only request_id, decision, and reason_code"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                decide_location_party_identity,
                request.state.operator_session.operator.operator_id,
                location_id,
                case_id,
                payload["request_id"],
                payload["decision"],
                payload["reason_code"],
            )
        except Exception as exc:
            return failure(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
