"""OIDC routes for location-scoped business model canvas reads."""


def register_business_planning_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.business_planning_reads import (
        BusinessPlanningReadInvalid,
        list_location_business_model_canvases,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get("/operator/api/business-planning/{location_id}/canvases")
    async def location_business_model_canvases(
        request: Request,
        location_id: str,
        limit: str = "25",
        offset: str = "0",
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_business_model_canvases,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified business planning access is required"},
                headers=headers,
            )
        except BusinessPlanningReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location business planning read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.business_planning").warning(
                "Business planning read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Business planning read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)
