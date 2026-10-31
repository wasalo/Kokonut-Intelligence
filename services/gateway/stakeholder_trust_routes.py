"""OIDC route for location-scoped, reviewed stakeholder trust evidence."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator


class _StakeholderTrustResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StakeholderIdentityTrustEvidence(_StakeholderTrustResponseModel):
    evidence_id: UUID
    dimension: Literal["identity"]
    direction: Literal["supporting"]
    evidence_code: Literal[
        "verified_identifier", "document_review", "participant_confirmation", "community_review"
    ]
    match_method: Literal["manual", "exact_identifier", "verified_document", "community_review"]
    confidence: Decimal = Field(ge=0, le=1, max_digits=5, decimal_places=4)
    reviewed_at: AwareDatetime


class StakeholderTrustCursor(_StakeholderTrustResponseModel):
    reviewed_at: AwareDatetime
    evidence_id: UUID


class StakeholderTrustEvidencePage(_StakeholderTrustResponseModel):
    location_id: UUID
    party_id: UUID
    evidence: list[StakeholderIdentityTrustEvidence] = Field(max_length=50)
    next_cursor: StakeholderTrustCursor | None

    @model_validator(mode="after")
    def validate_cursor_matches_page(self):
        if self.next_cursor is not None:
            if not self.evidence:
                raise ValueError("a continuation cursor requires a nonempty page")
            last = self.evidence[-1]
            if (
                self.next_cursor.reviewed_at != last.reviewed_at
                or self.next_cursor.evidence_id != last.evidence_id
            ):
                raise ValueError("continuation cursor must identify the last item")
        return self


class StakeholderTrustError(_StakeholderTrustResponseModel):
    error: str


def _trust_page_matches_request(
    page, *, location_id, party_id, limit, cursor_reviewed_at, cursor_evidence_id
):
    if (
        page.location_id != UUID(location_id)
        or page.party_id != UUID(party_id)
        or len(page.evidence) > limit
        or (cursor_reviewed_at is None) != (cursor_evidence_id is None)
    ):
        return False
    if page.next_cursor is not None and len(page.evidence) != limit:
        return False
    keys = [(item.reviewed_at, item.evidence_id) for item in page.evidence]
    if any(left <= right for left, right in zip(keys, keys[1:])):
        return False
    if cursor_reviewed_at is not None and cursor_evidence_id is not None:
        cursor_time = datetime.fromisoformat(cursor_reviewed_at.replace("Z", "+00:00"))
        cursor_key = (cursor_time, UUID(cursor_evidence_id))
        if any(key >= cursor_key for key in keys):
            return False
    return True


def register_stakeholder_trust_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.stakeholder_trust import (
        StakeholderTrustInvalid,
        list_location_identity_trust_evidence,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    trust_error_responses = {
        status: {"model": StakeholderTrustError, "description": description}
        for status, description in {
            400: "The trust-evidence cursor is invalid.",
            403: "The operator lacks current location-scoped trust access.",
            404: "Operator OIDC is disabled.",
            500: "The trust-evidence projection failed its response contract.",
            503: "The trust-evidence service is unavailable.",
        }.items()
    }

    @router.get(
        "/operator/api/stakeholder-trust/{location_id}/parties/{party_id}/identity-evidence",
        response_model=StakeholderTrustEvidencePage,
        responses=trust_error_responses,
    )
    async def location_identity_trust_evidence(
        request: Request,
        location_id: str,
        party_id: str,
        limit: int = Query(default=50, ge=1, le=50),
        cursor_reviewed_at: str | None = None,
        cursor_evidence_id: str | None = None,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_identity_trust_evidence,
                request.state.operator_session.operator.operator_id,
                location_id,
                party_id,
                limit=limit,
                cursor_reviewed_at=cursor_reviewed_at,
                cursor_evidence_id=cursor_evidence_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trust access is required"},
                headers=headers,
            )
        except StakeholderTrustInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location trust grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Trust evidence request is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.stakeholder_trust").warning(
                "Stakeholder trust request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Stakeholder trust service unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = StakeholderTrustEvidencePage.model_validate(result)
            if not _trust_page_matches_request(
                page,
                location_id=location_id,
                party_id=party_id,
                limit=limit,
                cursor_reviewed_at=cursor_reviewed_at,
                cursor_evidence_id=cursor_evidence_id,
            ):
                raise ValueError("trust-evidence page does not match request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.stakeholder_trust").warning(
                "Stakeholder trust response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Stakeholder trust evidence unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="python")),
            headers=headers,
        )
