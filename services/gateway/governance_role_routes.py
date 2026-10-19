"""OIDC route registration for location-scoped governance reads and actions."""


def register_governance_role_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.governance_assignment_proposal_reads import (
        GovernanceAssignmentProposalReadInvalid,
        list_own_governance_assignment_proposals,
    )
    from services.gateway.governance_assignment_proposals import (
        GovernanceAssignmentConflict,
        GovernanceAssignmentInvalid,
        propose_governance_role_assignment,
    )
    from services.gateway.governance_operations import (
        GovernanceOperationsInvalid,
        get_location_governance_role_detail,
        list_location_governance_roles,
        list_location_governance_tactical_items,
    )
    from services.gateway.governance_roles import get_location_governance_summary
    from services.gateway.governance_tension_actions import (
        GovernanceTensionConflict,
        GovernanceTensionInvalid,
        report_governance_tension,
        submit_governance_tension,
    )
    from services.gateway.governance_tension_review import (
        GovernanceTensionReviewInvalid,
        GovernanceTensionReviewNotFound,
        get_location_governance_tension,
        list_location_governance_tensions,
    )

    def error_response(exc, *, headers):
        if isinstance(exc, TenantContextDenied):
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        if isinstance(exc, GovernanceTensionInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionReviewInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionConflict):
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionReviewNotFound):
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, psycopg2.Error):
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance action grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance tension request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance tension request conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension action unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tension action unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        raise exc

    @router.get("/operator/api/governance/{location_id}/summary")
    async def location_governance_summary(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            summary = await run_in_threadpool(
                get_location_governance_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers=headers,
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )

        return JSONResponse(jsonable_encoder(summary), headers=headers)

    @router.get("/operator/api/governance/{location_id}/roles")
    async def location_governance_roles(
        request: Request,
        location_id: str,
        status: str | None = None,
        limit: str = "50",
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_roles,
                request.state.operator_session.operator.operator_id,
                location_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance role registry unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role registry unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/governance/{location_id}/roles/{role_id}")
    async def location_governance_role_detail(
        request: Request,
        location_id: str,
        role_id: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_role_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                role_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance role detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Governance role not found"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/assignment-proposals"
    )
    async def own_governance_assignment_proposals(
        request: Request,
        location_id: str,
        limit: str = "50",
        cursor_created_at: str | None = None,
        cursor_assignment_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_own_governance_assignment_proposals,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_assignment_id=cursor_assignment_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentProposalReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active governance role read grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance role proposal cursor is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role proposal readback unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role proposal readback unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/governance/{location_id}/roles/{role_id}/assignments",
        status_code=201,
    )
    async def propose_governance_role_assignment_route(
        request: Request, location_id: str, role_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Role nomination must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_governance_role_assignment,
                request.state.operator_session.operator.operator_id,
                location_id,
                role_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceAssignmentConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance role creation grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance role nomination is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance role nomination conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role nomination unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role nomination unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.get("/operator/api/governance/{location_id}/tactical-items")
    async def location_governance_tactical_items(
        request: Request,
        location_id: str,
        limit: str = "50",
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tactical_items,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor=cursor,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/governance/{location_id}/tensions")
    async def location_governance_tensions(
        request: Request,
        location_id: str,
        status: str | None = None,
        limit: str = "50",
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tensions,
                request.state.operator_session.operator.operator_id,
                location_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        except (
            TenantContextDenied,
            GovernanceTensionReviewInvalid,
            GovernanceTensionReviewNotFound,
            psycopg2.Error,
        ) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/governance/{location_id}/tensions/{tension_id}")
    async def location_governance_tension_detail(
        request: Request, location_id: str, tension_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                tension_id,
            )
        except (
            TenantContextDenied,
            GovernanceTensionReviewInvalid,
            GovernanceTensionReviewNotFound,
            psycopg2.Error,
        ) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/governance/{location_id}/tensions", status_code=201)
    async def create_governance_tension(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance tension content must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                report_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except (TenantContextDenied, GovernanceTensionInvalid, GovernanceTensionConflict, psycopg2.Error) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.post(
        "/operator/api/governance/{location_id}/tensions/{tension_id}/submit"
    )
    async def submit_governance_tension_route(
        request: Request, location_id: str, tension_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                tension_id,
            )
        except (TenantContextDenied, GovernanceTensionInvalid, GovernanceTensionConflict, psycopg2.Error) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), headers=headers)
