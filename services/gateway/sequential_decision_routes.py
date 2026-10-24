"""OIDC routes for location-scoped sequential evidence summaries."""


def register_sequential_decision_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.sequential_decision_reads import (
        SequentialDecisionReadInvalid,
        SequentialDecisionResponseTooLarge,
        get_location_sequential_decision_summary,
        list_location_sequential_evidence_timeline,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get("/operator/api/sequential-evidence/{location_id}/summary")
    async def location_sequential_decision_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_sequential_decision_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified sequential evidence access is required"},
                headers=headers,
            )
        except SequentialDecisionReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location sequential evidence read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.sequential_evidence").warning(
                "Sequential evidence summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Sequential evidence summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/sequential-evidence/{location_id}/events")
    async def location_sequential_evidence_timeline(
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
                list_location_sequential_evidence_timeline,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified sequential evidence access is required"},
                headers=headers,
            )
        except SequentialDecisionReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SequentialDecisionResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location sequential evidence read grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "22023":
                return JSONResponse(status_code=400, content={"error": "Sequential evidence page is invalid"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.sequential_evidence").warning(
                "Sequential evidence timeline unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Sequential evidence timeline unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)
