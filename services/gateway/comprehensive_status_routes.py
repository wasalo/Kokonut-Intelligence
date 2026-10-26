"""OIDC routes for location-scoped Comprehensive Status reports."""


def register_comprehensive_status_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.comprehensive_status_reads import (
        MAX_COMPREHENSIVE_STATUS_BYTES,
        ComprehensiveStatusPayloadTooLarge,
        ComprehensiveStatusReadInvalid,
        get_location_comprehensive_status,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get("/operator/api/comprehensive-status/{location_id}")
    async def location_comprehensive_status(
        request: Request,
        location_id: str,
        period_start: str | None = None,
        period_end: str | None = None,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_comprehensive_status,
                request.state.operator_session.operator.operator_id,
                location_id,
                period_start=period_start,
                period_end=period_end,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "A tenant-qualified Comprehensive Status read grant is required"},
                headers=headers,
            )
        except ComprehensiveStatusReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except ComprehensiveStatusPayloadTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location Comprehensive Status read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.comprehensive_status").warning(
                "Comprehensive Status read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Comprehensive Status read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        response = JSONResponse(jsonable_encoder(result), headers=headers)
        if len(response.body) > MAX_COMPREHENSIVE_STATUS_BYTES:
            return JSONResponse(
                status_code=413,
                content={"error": "Comprehensive Status exceeds the 512 KiB response limit"},
                headers=headers,
            )
        return response
