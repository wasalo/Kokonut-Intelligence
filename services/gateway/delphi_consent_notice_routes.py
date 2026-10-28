"""OIDC routes for drafting and independently reviewing Delphi consent notices."""

import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
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
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,39}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class _ConsentNoticeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _ConsentNoticeReviewItem(_ConsentNoticeResponse):
    notice_id: _StrictUuid
    study_id: _StrictUuid
    study_title: str = Field(max_length=255)
    version: str = Field(max_length=40, pattern=_VERSION_PATTERN.pattern)
    notice_text: str = Field(min_length=1, max_length=12000)
    notice_digest: str = Field(pattern=_DIGEST_PATTERN.pattern)
    created_at: AwareDatetime
    review_ready: bool
    blocked_reasons: list[Literal["self_review"]] = Field(max_length=1)
    # Empty scopes are valid for legacy notices created before migration 641.
    collection_scopes: list[Literal["questionnaire_responses", "minority_reports"]] = Field(
        max_length=2
    )

    @model_validator(mode="after")
    def validate_review_state(self):
        if not self.notice_text.strip():
            raise ValueError("Consent notice text must not be blank")
        if len(set(self.collection_scopes)) != len(self.collection_scopes):
            raise ValueError("Consent collection scopes must be unique")
        if self.review_ready != (not self.blocked_reasons):
            raise ValueError("Consent review readiness must match its blockers")
        return self


class _ConsentNoticeReviewPage(_ConsentNoticeResponse):
    location_id: _StrictUuid
    offset: int = Field(ge=0, le=10000)
    notices: list[_ConsentNoticeReviewItem] = Field(max_length=50)
    has_more: bool

    @model_validator(mode="after")
    def validate_page(self):
        if self.has_more and (not self.notices or self.offset >= 10000):
            raise ValueError("Consent notice continuation is outside the page bounds")
        return self


def register_delphi_consent_notice_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_consent_notices import (
        DelphiConsentNoticeInvalid,
        decide_location_delphi_consent_notice,
        list_location_delphi_consent_notices,
        submit_location_delphi_consent_notice,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location Delphi consent grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "The Delphi consent notice is not eligible for this action"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi consent notice request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_consent_notice").warning(
            "Delphi consent notice request unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi consent notice service unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    async def read_json_object(request: Request):
        body = await request.body()
        if len(body) > 65536:
            return None, JSONResponse(
                status_code=413,
                content={"error": "Delphi consent notice request is too large"},
                headers=headers,
            )
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "A JSON Delphi consent notice object is required"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "A JSON Delphi consent notice object is required"},
                headers=headers,
            )
        return payload, None

    @router.post("/operator/api/delphi/{location_id}/studies/{study_id}/consent-notices")
    async def submit_notice(request: Request, location_id: str, study_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers
            )
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        expected = {"request_id", "version", "notice_text", "collection_scopes"}
        if (
            set(payload) != expected
            or not all(
                isinstance(payload.get(key), str)
                for key in expected - {"collection_scopes"}
            )
            or not isinstance(payload.get("collection_scopes"), list)
            or not all(isinstance(scope, str) for scope in payload["collection_scopes"])
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Consent notice fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_delphi_consent_notice,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                version=payload["version"],
                notice_text=payload["notice_text"],
                collection_scopes=payload["collection_scopes"],
                request_id=payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi consent draft access is required"},
                headers=headers,
            )
        except DelphiConsentNoticeInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(
            jsonable_encoder(result), status_code=200 if result["replayed"] else 201, headers=headers
        )

    @router.get(
        "/operator/api/delphi/{location_id}/consent-notices",
        response_model=_ConsentNoticeReviewPage,
    )
    async def list_notices(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers
            )
        try:
            result = await run_in_threadpool(
                list_location_delphi_consent_notices,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi consent review access is required"},
                headers=headers,
            )
        except DelphiConsentNoticeInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        try:
            validated = _ConsentNoticeReviewPage.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.offset != offset
                or len(validated.notices) > limit
                or (
                    validated.has_more
                    and (len(validated.notices) != limit or offset + limit > 10000)
                )
            ):
                raise ValueError("Consent notice response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_consent_notice").warning(
                "Delphi consent notice response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi consent notice service unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )

    @router.post(
        "/operator/api/delphi/{location_id}/consent-notices/{notice_id}/decision"
    )
    async def decide_notice(request: Request, location_id: str, notice_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers
            )
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        expected = {"decision", "request_id", "reason_code"}
        if set(payload) != expected or not all(isinstance(payload.get(key), str) for key in expected):
            return JSONResponse(
                status_code=400, content={"error": "Consent decision fields are invalid"}, headers=headers
            )
        try:
            result = await run_in_threadpool(
                decide_location_delphi_consent_notice,
                request.state.operator_session.operator.operator_id,
                location_id,
                notice_id,
                decision=payload["decision"],
                request_id=payload["request_id"],
                reason_code=payload["reason_code"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi consent review access is required"},
                headers=headers,
            )
        except DelphiConsentNoticeInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
