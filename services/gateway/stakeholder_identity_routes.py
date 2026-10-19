"""OIDC routes for location-scoped stakeholder identity review."""


def register_stakeholder_identity_routes(router, provider, run_in_threadpool, psycopg2):
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

    @router.get("/operator/api/stakeholder-identity/{location_id}/cases")
    async def identity_review_queue(
        request: Request,
        location_id: str,
        limit: str = "50",
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
        return JSONResponse(jsonable_encoder(result), headers=headers)

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
