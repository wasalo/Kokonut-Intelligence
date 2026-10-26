"""OIDC routes for drafting and independently reviewing Delphi consent notices."""


def register_delphi_consent_notice_routes(router, provider, run_in_threadpool, psycopg2):
    import json

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

    @router.get("/operator/api/delphi/{location_id}/consent-notices")
    async def list_notices(
        request: Request, location_id: str, limit: str = "50", offset: str = "0"
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
        return JSONResponse(jsonable_encoder(result), headers=headers)

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
