"""OIDC route registration for location-scoped ecocredit reads."""


def register_ecocredit_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.ecocredits import list_location_ecocredit_batches

    @router.get("/operator/api/ecocredits/{location_id}/batches")
    async def location_ecocredit_batches(request: Request, location_id: str, limit: int = 50):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            rows = await run_in_threadpool(
                list_location_ecocredit_batches,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.ecocredits").warning(
                "Location ecocredit read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Location ecocredit read unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )

        return JSONResponse(
            {"data": jsonable_encoder(rows), "location_id": location_id},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
