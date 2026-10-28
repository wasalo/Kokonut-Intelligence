"""OIDC operator routes for issuing and revoking pseudonymous Delphi invites."""

import re
from datetime import datetime
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


def _strict_aware_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("datetime value is invalid") from exc
    else:
        raise ValueError("datetime values must be ISO strings or datetime objects")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime values must include a UTC offset")
    return parsed


_StrictUuid = Annotated[UUID, BeforeValidator(_strict_uuid)]
_StrictAwareDatetime = Annotated[AwareDatetime, BeforeValidator(_strict_aware_datetime)]
_NOTICE_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,39}$")


class _ParticipantInviteResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class _ParticipantInviteListItem(_ParticipantInviteResponseModel):
    invite_id: _StrictUuid
    study_id: _StrictUuid
    notice_version: str = Field(
        min_length=1, max_length=40, pattern=_NOTICE_VERSION_PATTERN.pattern
    )
    status: Literal["pending", "accepted", "revoked", "expired"]
    created_at: _StrictAwareDatetime
    expires_at: _StrictAwareDatetime

    @model_validator(mode="after")
    def validate_expiry(self):
        if self.expires_at <= self.created_at:
            raise ValueError("Invite expiry must follow creation")
        return self


class ParticipantInviteListResponse(_ParticipantInviteResponseModel):
    location_id: _StrictUuid
    study_id: _StrictUuid
    invites: list[_ParticipantInviteListItem] = Field(max_length=50)
    has_more: bool
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=10000)

    @model_validator(mode="after")
    def validate_projection(self):
        if any(invite.study_id != self.study_id for invite in self.invites):
            raise ValueError("Invite belongs to a different study")
        keys = [(invite.created_at, invite.invite_id) for invite in self.invites]
        if any(left <= right for left, right in zip(keys, keys[1:])):
            raise ValueError("Invites are not in canonical descending order")
        if self.has_more and (
            len(self.invites) != self.limit or self.offset + self.limit > 10000
        ):
            raise ValueError("Invite continuation exceeds its page bounds")
        return self


def register_delphi_participant_invite_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_participant_invites import (
        DelphiParticipantInviteInvalid,
        issue_location_delphi_participant_invite,
        list_location_delphi_participant_invites,
        revoke_location_delphi_participant_invite,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location Delphi invite grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "The Delphi invite or consent notice is not eligible"},
                headers=headers,
            )
        if code == "54000":
            return JSONResponse(
                status_code=409,
                content={"error": "The study has reached its pending invite limit"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi invite request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_participant_invite").warning(
            "Delphi invite request unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi invite service unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    async def read_json_object(request: Request):
        body = await request.body()
        if len(body) > 16384:
            return None, JSONResponse(
                status_code=413,
                content={"error": "Delphi invite request is too large"},
                headers=headers,
            )
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "A JSON Delphi invite object is required"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "A JSON Delphi invite object is required"},
                headers=headers,
            )
        return payload, None

    @router.get(
        "/operator/api/delphi/{location_id}/studies/{study_id}/invites",
        response_model=ParticipantInviteListResponse,
    )
    async def list_invites(
        request: Request,
        location_id: str,
        study_id: str,
        limit: int = Query(default=50, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers
            )
        try:
            result = await run_in_threadpool(
                list_location_delphi_participant_invites,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi invite access is required"},
                headers=headers,
            )
        except DelphiParticipantInviteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        try:
            page = ParticipantInviteListResponse.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.study_id != UUID(study_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Invite page does not match request scope")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_participant_invite").warning(
                "Delphi invite inventory response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi invite service unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="json")), headers=headers
        )

    @router.post("/operator/api/delphi/{location_id}/studies/{study_id}/invites")
    async def issue_invite(request: Request, location_id: str, study_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers
            )
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        expected = {"request_id", "lifetime_seconds"}
        if (
            set(payload) != expected
            or not isinstance(payload.get("request_id"), str)
            or isinstance(payload.get("lifetime_seconds"), bool)
            or not isinstance(payload.get("lifetime_seconds"), int)
        ):
            return JSONResponse(
                status_code=400, content={"error": "Delphi invite fields are invalid"}, headers=headers
            )
        try:
            result = await run_in_threadpool(
                issue_location_delphi_participant_invite,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                lifetime_seconds=payload["lifetime_seconds"],
                request_id=payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi invite access is required"},
                headers=headers,
            )
        except DelphiParticipantInviteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/delphi/{location_id}/invites/{invite_id}/revoke"
    )
    async def revoke_invite(request: Request, location_id: str, invite_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers
            )
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        expected = {"request_id", "reason_code"}
        if set(payload) != expected or not all(
            isinstance(payload.get(key), str) for key in expected
        ):
            return JSONResponse(
                status_code=400, content={"error": "Delphi revoke fields are invalid"}, headers=headers
            )
        try:
            result = await run_in_threadpool(
                revoke_location_delphi_participant_invite,
                request.state.operator_session.operator.operator_id,
                location_id,
                invite_id,
                request_id=payload["request_id"],
                reason_code=payload["reason_code"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi invite revoke access is required"},
                headers=headers,
            )
        except DelphiParticipantInviteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
