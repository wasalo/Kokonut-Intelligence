"""OIDC operator routes for issuing and revoking pseudonymous Delphi invites."""


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
        "/operator/api/delphi/{location_id}/studies/{study_id}/invites"
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
        return JSONResponse(jsonable_encoder(result), headers=headers)

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
