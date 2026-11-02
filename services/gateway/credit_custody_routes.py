"""OIDC route registration for aggregate credit-custody reads."""


def register_credit_custody_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Response
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.credit_custody import get_credit_custody_summary
    from services.gateway.credit_custody_models import CreditCustodySummaryResponse

    @router.get(
        "/operator/api/credit-custody/{location_id}/summary",
        response_model=CreditCustodySummaryResponse,
    )
    async def credit_custody_summary(
        request: Request,
        location_id: str,
        response: Response,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            summary = await run_in_threadpool(
                get_credit_custody_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
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

            get_logger("gateway.credit_custody").warning(
                "Credit-custody summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Credit-custody summary unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )

        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Cookie"
        return jsonable_encoder(summary)
