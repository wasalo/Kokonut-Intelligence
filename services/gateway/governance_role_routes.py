"""OIDC route registration for location-scoped governance reads and actions."""


def register_governance_role_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.governance_roles import get_location_governance_summary
    from services.gateway.governance_tension_actions import (
        GovernanceTensionConflict,
        GovernanceTensionInvalid,
        report_governance_tension,
        submit_governance_tension,
    )
    from services.gateway.governance_tension_review import (
        GovernanceTensionReviewInvalid,
        GovernanceTensionReviewNotFound,
        get_location_governance_tension,
        list_location_governance_tensions,
    )

    def error_response(exc, *, headers):
        if isinstance(exc, TenantContextDenied):
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        if isinstance(exc, GovernanceTensionInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionReviewInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionConflict):
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionReviewNotFound):
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, psycopg2.Error):
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance action grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance tension request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance tension request conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension action unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tension action unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        raise exc

    @router.get("/operator/api/governance/{location_id}/summary")
    async def location_governance_summary(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            summary = await run_in_threadpool(
                get_location_governance_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers=headers,
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )

        return JSONResponse(jsonable_encoder(summary), headers=headers)

    @router.get("/operator/api/governance/{location_id}/tensions")
    async def location_governance_tensions(
        request: Request,
        location_id: str,
        status: str | None = None,
        limit: str = "50",
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tensions,
                request.state.operator_session.operator.operator_id,
                location_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        except (
            TenantContextDenied,
            GovernanceTensionReviewInvalid,
            GovernanceTensionReviewNotFound,
            psycopg2.Error,
        ) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/governance/{location_id}/tensions/{tension_id}")
    async def location_governance_tension_detail(
        request: Request, location_id: str, tension_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                tension_id,
            )
        except (
            TenantContextDenied,
            GovernanceTensionReviewInvalid,
            GovernanceTensionReviewNotFound,
            psycopg2.Error,
        ) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/governance/{location_id}/tensions", status_code=201)
    async def create_governance_tension(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance tension content must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                report_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except (TenantContextDenied, GovernanceTensionInvalid, GovernanceTensionConflict, psycopg2.Error) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.post(
        "/operator/api/governance/{location_id}/tensions/{tension_id}/submit"
    )
    async def submit_governance_tension_route(
        request: Request, location_id: str, tension_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                tension_id,
            )
        except (TenantContextDenied, GovernanceTensionInvalid, GovernanceTensionConflict, psycopg2.Error) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), headers=headers)
