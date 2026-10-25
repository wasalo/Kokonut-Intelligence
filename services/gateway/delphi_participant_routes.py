"""Public capability-token routes for pseudonymous Delphi participants."""


def register_delphi_participant_routes(router, run_in_threadpool, psycopg2):
    import hmac
    import json

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.gateway.delphi_participant_acceptance import (
        DelphiParticipantAcceptanceInvalid,
        accept_location_delphi_participant_invite,
        preview_location_delphi_participant_invite,
        withdraw_location_delphi_participant,
    )

    session_cookie = "kokonut_delphi_participant_session"
    csrf_cookie = "kokonut_delphi_participant_csrf"
    headers = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "Vary": "Cookie",
    }

    async def read_json_object(request: Request):
        body = await request.body()
        if len(body) > 16384:
            return None, JSONResponse(
                status_code=413,
                content={"error": "Delphi participant request is too large"},
                headers=headers,
            )
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "A JSON Delphi participant object is required"},
                headers=headers,
            )
        return payload, None

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=401,
                content={"error": "Delphi participant access is invalid or unavailable"},
                headers=headers,
            )
        if code in {"55000", "23505", "23514"}:
            return JSONResponse(
                status_code=409,
                content={"error": "Delphi participant state changed; reload and try again"},
                headers=headers,
            )
        if code in {"22023", "22P02"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi participant request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_participant").warning(
            "Delphi participant request unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi participant service unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.post("/participation/delphi/preview")
    async def preview_invite(request: Request):
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        if set(payload) != {"invite_token"} or not isinstance(payload.get("invite_token"), str):
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi invite preview fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                preview_location_delphi_participant_invite,
                payload["invite_token"],
            )
        except DelphiParticipantAcceptanceInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/participation/delphi/accept")
    async def accept_invite(request: Request):
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        expected = {
            "invite_token",
            "notice_digest",
            "session_token",
            "csrf_token",
            "request_id",
            "accepted",
        }
        if (
            set(payload) != expected
            or not all(isinstance(payload.get(key), str) for key in expected - {"accepted"})
            or not isinstance(payload.get("accepted"), bool)
            or payload.get("accepted") is not True
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Explicit Delphi consent acceptance is required"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                accept_location_delphi_participant_invite,
                payload["invite_token"],
                payload["notice_digest"],
                payload["session_token"],
                payload["csrf_token"],
                payload["request_id"],
                accepted=payload["accepted"],
            )
        except DelphiParticipantAcceptanceInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        response = JSONResponse(
            jsonable_encoder({
                "status": result["status"],
                "notice_version": result["notice_version"],
                "accepted_at": result["accepted_at"],
                "session_expires_at": result["session_expires_at"],
                "replayed": result["replayed"],
            }),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )
        # The browser creates both random values before submitting consent, so it
        # can repeat a lost response exactly. They are never echoed in JSON.
        response.set_cookie(
            session_cookie,
            payload["session_token"],
            max_age=30 * 24 * 60 * 60,
            path="/api/participation/delphi",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        response.set_cookie(
            csrf_cookie,
            payload["csrf_token"],
            max_age=30 * 24 * 60 * 60,
            path="/api/participation/delphi",
            secure=True,
            httponly=False,
            samesite="strict",
        )
        return response

    @router.post("/participation/delphi/withdraw")
    async def withdraw(request: Request):
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        if set(payload) != {"request_id"} or not isinstance(payload.get("request_id"), str):
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi withdrawal request fields are invalid"},
                headers=headers,
            )
        session_token = request.cookies.get(session_cookie, "")
        csrf_cookie_value = request.cookies.get(csrf_cookie, "")
        csrf_header_value = request.headers.get("x-kokonut-csrf", "")
        if (
            not csrf_cookie_value
            or not csrf_header_value
            or not hmac.compare_digest(csrf_cookie_value, csrf_header_value)
        ):
            return JSONResponse(
                status_code=403,
                content={"error": "Delphi withdrawal CSRF validation failed"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                withdraw_location_delphi_participant,
                session_token,
                csrf_header_value,
                payload["request_id"],
            )
        except DelphiParticipantAcceptanceInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        response = JSONResponse(jsonable_encoder(result), headers=headers)
        response.delete_cookie(
            session_cookie,
            path="/api/participation/delphi",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        response.delete_cookie(
            csrf_cookie,
            path="/api/participation/delphi",
            secure=True,
            httponly=False,
            samesite="strict",
        )
        return response
