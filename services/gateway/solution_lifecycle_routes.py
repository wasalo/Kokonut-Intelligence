"""OIDC routes for location-scoped solution lifecycle reads."""


def register_solution_lifecycle_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.solution_lifecycle_reads import (
        SolutionLifecycleReadInvalid,
        SolutionLifecycleResponseTooLarge,
        get_location_solution_lifecycle_summary,
        list_location_solution_experiments,
        list_location_solution_funding,
        list_location_solution_gates,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get("/operator/api/solution-lifecycle/{location_id}/summary")
    async def location_solution_lifecycle_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_lifecycle_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/funding")
    async def location_solution_lifecycle_funding(
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
                list_location_solution_funding,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle funding unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle funding unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/gates")
    async def location_solution_lifecycle_gates(
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
                list_location_solution_gates,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle gates unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle gates unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/experiments")
    async def location_solution_lifecycle_experiments(
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
                list_location_solution_experiments,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle experiments unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle experiments unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)
