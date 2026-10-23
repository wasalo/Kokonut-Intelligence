"""OIDC route registration for location-scoped nutrient balance reads."""


def register_nutrient_balance_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.nutrient_balances import get_location_nutrient_balances

    @router.get("/operator/api/nutrients/{location_id}/balances")
    async def nutrient_balances(
        request: Request,
        location_id: str,
        limit: int = 25,
        offset: int = 0,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_nutrient_balances,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
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

            get_logger("gateway.nutrient_balances").warning(
                "Nutrient balances unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Nutrient balances unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )
        return JSONResponse(
            jsonable_encoder(result),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
