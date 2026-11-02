"""OIDC routes for location-scoped Delphi facilitator draft creation."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
)


def _strict_uuid(value):
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise ValueError("UUID values must be strings")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("UUID value is invalid") from exc


_StrictUuid = Annotated[UUID, BeforeValidator(_strict_uuid)]


class _DraftStudyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    study_id: _StrictUuid
    title: str = Field(max_length=255)
    status: Literal["open", "closed"]
    updated_at: AwareDatetime | None


class DelphiDraftStudyPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    location_id: _StrictUuid
    offset: int = Field(ge=0, le=10_000)
    studies: list[_DraftStudyResponse] = Field(max_length=50)
    has_more: bool

    def validate_request(self, *, location_id: UUID, limit: int, offset: int):
        if self.location_id != location_id or self.offset != offset:
            raise ValueError("response scope does not match request")
        if len(self.studies) > limit:
            raise ValueError("response exceeds requested page size")
        if self.has_more and (
            len(self.studies) != limit or offset + limit > 10_000
        ):
            raise ValueError("response continuation exceeds requested bounds")
        return self


class DelphiRecommendationDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    recommendation_id: _StrictUuid
    study_id: _StrictUuid
    status: Literal["draft", "approved", "rejected"]
    created_at: AwareDatetime


def register_delphi_recommendation_draft_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_recommendation_drafts import (
        DelphiDraftInvalid,
        create_location_delphi_recommendation_draft,
        list_location_delphi_draftable_studies,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location Delphi draft grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "Drafts require an open or closed Delphi study"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi draft request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_recommendation_drafts").warning(
            "Delphi recommendation draft unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi recommendation draft unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.get(
        "/operator/api/delphi/{location_id}/draft-studies",
        response_model=DelphiDraftStudyPage,
    )
    async def list_draftable_studies(
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
                list_location_delphi_draftable_studies,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi draft access is required"},
                headers=headers,
            )
        except DelphiDraftInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        try:
            page = DelphiDraftStudyPage.model_validate(result)
            page.validate_request(
                location_id=UUID(location_id), limit=limit, offset=offset
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_recommendation_drafts").warning(
                "Delphi draft-study response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi draft-study list unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="json")), headers=headers
        )

    @router.post(
        "/operator/api/delphi/{location_id}/studies/{study_id}/recommendation-drafts",
        response_model=DelphiRecommendationDraftResponse,
    )
    async def create_recommendation_draft(
        request: Request,
        location_id: str,
        study_id: str,
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
                content={"error": "A JSON recommendation draft object is required"},
                headers=headers,
            )
        if (
            not isinstance(payload, dict)
            or set(payload) != {"request_id", "summary", "recommendation_text"}
            or not isinstance(payload.get("request_id"), str)
            or not isinstance(payload.get("recommendation_text"), str)
            or (payload.get("summary") is not None and not isinstance(payload.get("summary"), str))
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Recommendation draft fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_delphi_recommendation_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                request_id=payload["request_id"],
                summary=payload["summary"],
                recommendation_text=payload["recommendation_text"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi draft access is required"},
                headers=headers,
            )
        except DelphiDraftInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        try:
            validated = DelphiRecommendationDraftResponse.model_validate(result)
            if validated.study_id != UUID(study_id):
                raise ValueError("Recommendation draft response does not match request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_recommendation_drafts").warning(
                "Delphi recommendation draft response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi recommendation draft unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
