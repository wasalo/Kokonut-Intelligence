"""OIDC routes for location-scoped, advisory-only backcast readback."""


def register_threatcasting_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.threatcasting_reads import (
        ThreatcastingReadInvalid,
        ThreatcastingReadTooLarge,
        get_location_backcast_plan,
        list_location_backcast_plans,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def unavailable(exc):
        from services.common.logging import get_logger

        get_logger("gateway.threatcasting").warning(
            "Threatcasting read unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Threatcasting read unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    def tenant_denied():
        return JSONResponse(
            status_code=403,
            content={"error": "Tenant-qualified operator access is required"},
            headers=headers,
        )

    @router.get("/operator/api/threatcasting/{location_id}/backcast-plans")
    async def location_backcast_plans(
        request: Request,
        location_id: str,
        limit: str = "50",
        cursor_created_at: str | None = None,
        cursor_plan_id: str | None = None,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_backcast_plans,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_plan_id=cursor_plan_id,
            )
        except TenantContextDenied:
            return tenant_denied()
        except ThreatcastingReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return tenant_denied()
            return unavailable(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/threatcasting/{location_id}/backcast-plans/{plan_id}"
    )
    async def location_backcast_plan(request: Request, location_id: str, plan_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_backcast_plan,
                request.state.operator_session.operator.operator_id,
                location_id,
                plan_id,
            )
        except TenantContextDenied:
            return tenant_denied()
        except ThreatcastingReadTooLarge:
            return JSONResponse(
                status_code=413,
                content={"error": "Backcast plan exceeds the maximum readable response size"},
                headers=headers,
            )
        except ThreatcastingReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return tenant_denied()
            return unavailable(exc)
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Backcast plan not found in this location"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)
