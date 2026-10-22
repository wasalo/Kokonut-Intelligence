"""OIDC routes for location-scoped operating-pilot reads and private drafts."""


def register_operating_pilot_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.operating_pilot_reads import (
        OperatingPilotReadInvalid,
        get_location_operating_pilot_capacity_periods,
        get_location_operating_pilot_capacity_review_queue,
        get_location_operating_pilot_demand_signals,
        get_location_operating_pilot_own_capacity_profiles,
        get_location_operating_pilot_resource_categories,
        get_location_operating_pilot_summary,
        get_location_operating_pilot_work_claims,
    )
    from services.gateway.operating_pilot_writes import (
        OperatingPilotWriteInvalid,
        create_location_operating_pilot_capacity_draft,
        create_location_operating_pilot_demand_draft,
        review_location_operating_pilot_capacity,
        revise_location_operating_pilot_capacity_draft,
        submit_location_operating_pilot_capacity_draft,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.post("/operator/api/operating-pilot/{location_id}/capacity-profiles")
    async def create_operating_pilot_capacity_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity draft body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity draft body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_capacity_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot create access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location create grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "A capacity profile already exists for this person and period, or the request conflicts"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Capacity draft input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.put("/operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}")
    async def revise_operating_pilot_capacity_draft(request: Request, location_id: str, profile_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity revision body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity revision body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_capacity_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                profile_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot edit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location edit-own grant and editable personal capacity record are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "A capacity profile already exists for this person and period, or the request conflicts"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Capacity revision input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}/submit"
    )
    async def submit_operating_pilot_capacity_draft(request: Request, location_id: str, profile_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity submission body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity submission requires only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_capacity_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                profile_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot submit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location submit-own grant and editable personal draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The submission request ID conflicts with another capacity profile"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The capacity draft changed; refresh before trying again"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/operating-pilot/{location_id}/demand-signals")
    async def create_operating_pilot_demand_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand draft body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Demand draft body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_demand_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot create access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot create grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Request ID was already used with different demand input"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Demand draft input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning("Operating demand draft unavailable (%s)", type(exc).__name__)
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/summary")
    async def location_operating_pilot_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating pilot summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating pilot summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/demand-signals")
    async def location_operating_pilot_demand_signals(
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
                get_location_operating_pilot_demand_signals,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning("Operating demand read unavailable (%s)", type(exc).__name__)
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/capacity-periods")
    async def location_operating_pilot_capacity_periods(
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
                get_location_operating_pilot_capacity_periods,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/my-capacity-profiles")
    async def location_operating_pilot_own_capacity_profiles(
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
                get_location_operating_pilot_own_capacity_profiles,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-capacity access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location own-capacity grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own-capacity page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own operating capacity read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own operating capacity read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/capacity-review-queue")
    async def location_operating_pilot_capacity_review_queue(
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
                get_location_operating_pilot_capacity_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified capacity review access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Capacity review page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}/review"
    )
    async def review_operating_pilot_capacity_profile(
        request: Request, location_id: str, profile_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_capacity,
                request.state.operator_session.operator.operator_id,
                location_id,
                profile_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot review access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The review request conflicts or this submission already has a decision"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Capacity review decision or reason is invalid"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity review decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/work-claims")
    async def location_operating_pilot_work_claims(
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
                get_location_operating_pilot_work_claims,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-claim read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/resource-categories")
    async def location_operating_pilot_resource_categories(
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
                get_location_operating_pilot_resource_categories,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)
