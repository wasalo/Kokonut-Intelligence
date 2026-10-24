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
        get_location_operating_pilot_competency_review_queue,
        get_location_operating_pilot_demand_review_queue,
        get_location_operating_pilot_demand_signals,
        get_location_operating_pilot_own_capacity_profiles,
        get_location_operating_pilot_own_competency_drafts,
        get_location_operating_pilot_own_demand_signals,
        get_location_operating_pilot_own_resource_requests,
        get_location_operating_pilot_resource_categories,
        get_location_operating_pilot_resource_fulfillment_queue,
        get_location_operating_pilot_resource_review_queue,
        get_location_operating_pilot_summary,
        get_location_operating_pilot_work_claim_allocation_queue,
        get_location_operating_pilot_work_claim_review_queue,
        get_location_operating_pilot_work_claims,
        get_location_operating_pilot_work_opportunities,
    )
    from services.gateway.operating_pilot_writes import (
        OperatingPilotWriteInvalid,
        allocate_location_operating_pilot_work_claim,
        claim_location_operating_pilot_work,
        create_location_operating_pilot_capacity_draft,
        create_location_operating_pilot_competency_draft,
        create_location_operating_pilot_demand_draft,
        create_location_operating_pilot_resource_draft,
        fulfill_location_operating_pilot_resource_request,
        review_location_operating_pilot_capacity,
        review_location_operating_pilot_competency_assessment,
        review_location_operating_pilot_demand,
        review_location_operating_pilot_resource_request,
        review_location_operating_pilot_work_claim,
        revise_location_operating_pilot_capacity_draft,
        revise_location_operating_pilot_competency_draft,
        revise_location_operating_pilot_demand_draft,
        revise_location_operating_pilot_resource_draft,
        submit_location_operating_pilot_capacity_draft,
        submit_location_operating_pilot_competency_draft,
        submit_location_operating_pilot_demand_draft,
        submit_location_operating_pilot_resource_draft,
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

    @router.get("/operator/api/operating-pilot/{location_id}/work-claim-review-queue")
    async def location_operating_pilot_work_claim_review_queue(
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
                get_location_operating_pilot_work_claim_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot review access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and active reviewer binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Work-claim review page is outside its bounds"},
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
                "Operating work-claim review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/work-claims/{claim_id}/review"
    )
    async def review_location_operating_pilot_work_claim_route(
        request: Request,
        location_id: str,
        claim_id: str,
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
                content={"error": "Work-claim review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_work_claim,
                request.state.operator_session.operator.operator_id,
                location_id,
                claim_id,
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
                    content={"error": "A current exact location review grant and eligible claim are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The review request conflicts or the claim was already decided"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Work-claim decision or rejection reason is invalid"},
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
                "Operating work-claim review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/operating-pilot/{location_id}/work-claim-allocation-queue"
    )
    async def location_operating_pilot_work_claim_allocation_queue(
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
                get_location_operating_pilot_work_claim_allocation_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot allocation access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location allocation grant and active allocator binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Work-claim allocation page is outside its bounds"},
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
                "Operating work-claim allocation queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim allocation queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/work-claims/{claim_id}/allocate"
    )
    async def allocate_location_operating_pilot_work_claim_route(
        request: Request,
        location_id: str,
        claim_id: str,
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
                content={"error": "Work-claim allocation body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim allocation body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if payload:
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim allocation contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                allocate_location_operating_pilot_work_claim,
                request.state.operator_session.operator.operator_id,
                location_id,
                claim_id,
                request_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot allocation access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location allocation grant and eligible accepted claim are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The allocation request conflicts or the claim was already allocated"},
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
                "Operating work-claim allocation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim allocation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

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

    @router.post("/operator/api/operating-pilot/{location_id}/resource-requests")
    async def create_operating_pilot_resource_draft(request: Request, location_id: str):
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
                content={"error": "Resource draft body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Resource draft body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_resource_draft,
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
                    content={"error": "Resource draft request ID was reused with different input"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Resource draft input is invalid or outside its bounds"},
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
                "Operating resource draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.post("/operator/api/operating-pilot/{location_id}/competency-assessments")
    async def create_operating_pilot_competency_draft(request: Request, location_id: str):
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
                content={"error": "Competency draft body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Competency draft body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_competency_draft,
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
                    content={"error": "An open competency draft exists or the request conflicts"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Competency draft input is invalid or outside its bounds"},
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
                "Operating competency draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.put(
        "/operator/api/operating-pilot/{location_id}/competency-assessments/{draft_id}"
    )
    async def revise_operating_pilot_competency_draft(
        request: Request, location_id: str, draft_id: str
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
                content={"error": "Competency revision body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Competency revision body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_competency_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
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
                    content={"error": "A current exact location edit-own grant and editable personal competency assessment are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "A competency draft already exists or the revision request conflicts"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Competency revision input is invalid or outside its bounds"},
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
                    content={"error": "The competency assessment changed; refresh before trying again"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating competency revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/competency-assessments/{draft_id}/submit"
    )
    async def submit_operating_pilot_competency_draft(
        request: Request, location_id: str, draft_id: str
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
                content={"error": "Competency submission body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Competency submission requires only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_competency_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
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
                    content={"error": "A current exact location submit-own grant and editable personal competency draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The submission request ID conflicts with another competency assessment"},
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
                    content={"error": "The competency assessment changed; refresh before trying again"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating competency submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.put("/operator/api/operating-pilot/{location_id}/resource-requests/{draft_id}")
    async def revise_operating_pilot_resource_draft(request: Request, location_id: str, draft_id: str):
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
                content={"error": "Resource revision body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Resource revision body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_resource_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
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
                    content={"error": "A current exact location edit-own grant and editable personal resource draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Resource revision request conflicts or the draft is no longer editable"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The resource draft changed; refresh before trying again"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Resource revision input is invalid or outside its bounds"},
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
                "Operating resource revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/resource-requests/{draft_id}/submit"
    )
    async def submit_operating_pilot_resource_draft(
        request: Request, location_id: str, draft_id: str
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
                content={"error": "Resource submission body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource submission requires only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_resource_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
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
                    content={"error": "A current exact location submit-own grant and owned resource draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The resource submission conflicts or this draft is already submitted"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The resource draft changed; refresh before trying again"},
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
                "Operating resource submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}/submit"
    )
    async def submit_operating_pilot_demand_draft(
        request: Request, location_id: str, signal_id: str
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
                content={"error": "Demand submission body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand submission accepts only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_demand_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                signal_id,
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
                    content={"error": "A current exact location submit-own grant and owned demand draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The demand submission conflicts or this draft is already submitted"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The demand draft changed; refresh before trying again"},
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
                "Operating demand submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.put("/operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}")
    async def revise_operating_pilot_demand_draft(request: Request, location_id: str, signal_id: str):
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
                content={"error": "Demand revision body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Demand revision body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_demand_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                signal_id,
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
                    content={"error": "A current exact location edit-own grant and editable personal demand draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Demand revision request conflicts or the record is no longer editable"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The demand draft changed; refresh before trying again"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Demand revision input is invalid or outside its bounds"},
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
                "Operating demand revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

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

    @router.get("/operator/api/operating-pilot/{location_id}/my-competency-assessments")
    async def location_operating_pilot_own_competency_drafts(
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
                get_location_operating_pilot_own_competency_drafts,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-competency access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location own-history grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own competency page is outside its bounds"},
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
                "Own competency history unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own competency history unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/my-demand-signals")
    async def location_operating_pilot_own_demand_signals(
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
                get_location_operating_pilot_own_demand_signals,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-demand access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location own-demand grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own-demand page is outside its bounds"},
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
                "Own operating demand read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own operating demand read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/my-resource-requests")
    async def location_operating_pilot_own_resource_requests(
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
                get_location_operating_pilot_own_resource_requests,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-resource access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location read_own grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own-resource page is outside its bounds"},
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
                "Own operating resource read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own operating resource read unavailable"},
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

    @router.get("/operator/api/operating-pilot/{location_id}/competency-review-queue")
    async def location_operating_pilot_competency_review_queue(
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
                get_location_operating_pilot_competency_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified competency review access is required"},
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
                    content={"error": "Competency review page is outside its bounds"},
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
                "Operating competency review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/demand-review-queue")
    async def location_operating_pilot_demand_review_queue(
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
                get_location_operating_pilot_demand_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified demand review access is required"},
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
                    content={"error": "Demand review page is outside its bounds"},
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
                "Operating demand review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/resource-review-queue")
    async def location_operating_pilot_resource_review_queue(
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
                get_location_operating_pilot_resource_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified resource review access is required"},
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
                    content={"error": "Resource review page is outside its bounds"},
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
                "Operating resource review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/resource-fulfillment-queue")
    async def location_operating_pilot_resource_fulfillment_queue(
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
                get_location_operating_pilot_resource_fulfillment_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified resource fulfillment access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location fulfillment grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Resource fulfillment page is outside its bounds"},
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
                "Operating resource fulfillment queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource fulfillment queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/resource-requests/{resource_request_id}/review"
    )
    async def review_operating_pilot_resource_request(
        request: Request, location_id: str, resource_request_id: str
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
                content={"error": "Resource review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Resource review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_resource_request,
                request.state.operator_session.operator.operator_id,
                location_id,
                resource_request_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified resource review access is required"},
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
                    content={"error": "Resource review decision or reason is invalid"},
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
                "Operating resource review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource review decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/resource-requests/{resource_request_id}/fulfill"
    )
    async def fulfill_operating_pilot_resource_request(
        request: Request, location_id: str, resource_request_id: str
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
                content={"error": "Resource fulfillment body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource fulfillment requires only a request ID"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                fulfill_location_operating_pilot_resource_request,
                request.state.operator_session.operator.operator_id,
                location_id,
                resource_request_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified resource fulfillment access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location fulfillment grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The fulfillment request conflicts or this resource was already fulfilled"},
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
                    content={"error": "The resource request changed before fulfillment was recorded"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource fulfillment unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource fulfillment unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/competency-assessments/{draft_id}/review"
    )
    async def review_operating_pilot_competency_assessment(
        request: Request, location_id: str, draft_id: str
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
                content={"error": "Competency review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Competency review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Competency review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_competency_assessment,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified competency review access is required"},
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
                    content={"error": "The competency review request conflicts or this assessment already has a decision"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Competency review decision or reason is invalid"},
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
                "Operating competency review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency review decision unavailable"},
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

    @router.post(
        "/operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}/review"
    )
    async def review_operating_pilot_demand_signal(
        request: Request, location_id: str, signal_id: str
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
                content={"error": "Demand review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Demand review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_demand,
                request.state.operator_session.operator.operator_id,
                location_id,
                signal_id,
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
                    content={"error": "Demand review decision or reason is invalid"},
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
                "Operating demand review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand review decision unavailable"},
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

    @router.get("/operator/api/operating-pilot/{location_id}/work-opportunities")
    async def location_operating_pilot_work_opportunities(
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
                get_location_operating_pilot_work_opportunities,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot claim-own access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location claim-own grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Work opportunity page is outside its bounds"},
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
                "Operating work-opportunity read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-opportunity read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/work-opportunities/{work_item_id}/claims"
    )
    async def claim_location_operating_pilot_work_route(
        request: Request,
        location_id: str,
        work_item_id: str,
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
                content={"error": "Work-claim body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"proposed_effort_hours"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Work claim contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                claim_location_operating_pilot_work,
                request.state.operator_session.operator.operator_id,
                location_id,
                work_item_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot claim-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location claim-own grant and open work opportunity are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The work-claim request conflicts or this person already has a claim"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Proposed work effort is invalid or outside its bounds"},
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
                "Operating work-claim proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)
