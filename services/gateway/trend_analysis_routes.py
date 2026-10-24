"""OIDC routes for saved, location-scoped trend-analysis outputs."""


def register_trend_analysis_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.trend_analysis_reads import (
        get_location_seasonal_decomposition,
        get_location_time_series_forecast,
        list_location_change_points,
        list_location_trend_estimates,
        list_location_trend_smoothing,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get("/operator/api/trends/{location_id}/estimates")
    async def trend_estimates(
        request: Request,
        location_id: str,
        limit: int = 25,
        offset: int = 0,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_trend_estimates,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend estimates unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend estimates unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/trends/{location_id}/change-points")
    async def trend_change_points(
        request: Request,
        location_id: str,
        metric_key: str,
        limit: int = 100,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_change_points,
                request.state.operator_session.operator.operator_id,
                location_id,
                metric_key,
                limit=limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend change-point read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend change-point read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/trends/{location_id}/decomposition")
    async def trend_decomposition(
        request: Request,
        location_id: str,
        metric_key: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_seasonal_decomposition,
                request.state.operator_session.operator.operator_id,
                location_id,
                metric_key,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend decomposition unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend decomposition unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/trends/{location_id}/forecast")
    async def trend_forecast(
        request: Request,
        location_id: str,
        metric_key: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_time_series_forecast,
                request.state.operator_session.operator.operator_id,
                location_id,
                metric_key,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend forecast unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend forecast unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/trends/{location_id}/smoothing")
    async def trend_smoothing(
        request: Request,
        location_id: str,
        metric_key: str,
        limit: int = 100,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_trend_smoothing,
                request.state.operator_session.operator.operator_id,
                location_id,
                metric_key,
                limit=limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend smoothing unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend smoothing unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)
