"""OIDC routes for draft-only business canvas edits and version history."""


def register_business_planning_edit_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.business_planning_edits import update_location_business_model_canvas_block
    from services.gateway.business_planning_reads import (
        BusinessPlanningHistoryTooLarge,
        BusinessPlanningReadInvalid,
        list_location_business_model_canvas_versions,
    )
    from services.gateway.business_planning_writes import BusinessPlanningWriteInvalid

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
    max_history_bytes = 524_288

    def _database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "Current location business planning access is required"},
                headers=headers,
            )
        if code == "P0002":
            return JSONResponse(
                status_code=404,
                content={"error": "Location business canvas was not found"},
                headers=headers,
            )
        if code in {"22023"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Business canvas edit or history request is invalid"},
                headers=headers,
            )
        if code in {"23505", "40001", "55000"}:
            return JSONResponse(
                status_code=409,
                content={"error": "Business canvas changed or is not editable in its current state"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.business_planning").warning(
            "Business canvas edit/history unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Business canvas edit/history unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.get(
        "/operator/api/business-planning/{location_id}/canvases/{canvas_id}/versions"
    )
    async def location_business_model_canvas_versions(
        request: Request,
        location_id: str,
        canvas_id: str,
        limit: str = "5",
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
                list_location_business_model_canvas_versions,
                request.state.operator_session.operator.operator_id,
                location_id,
                canvas_id,
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
        except BusinessPlanningHistoryTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return _database_error(exc)

        response = JSONResponse(jsonable_encoder(result), headers=headers)
        if len(response.body) > max_history_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": "Business canvas history exceeds 512 KiB"},
                headers=headers,
            )
        return response

    @router.patch(
        "/operator/api/business-planning/{location_id}/canvases/{canvas_id}/blocks/{block_name}"
    )
    async def update_location_business_model_canvas_block_route(
        request: Request,
        location_id: str,
        canvas_id: str,
        block_name: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "A business canvas edit JSON object is required"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "A business canvas edit JSON object is required"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                update_location_business_model_canvas_block,
                request.state.operator_session.operator.operator_id,
                location_id,
                canvas_id,
                block_name,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified business planning update access is required"},
                headers=headers,
            )
        except BusinessPlanningWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return _database_error(exc)
        return JSONResponse(
            jsonable_encoder(result),
            headers=headers,
        )
