"""OIDC routes for location-scoped solution lifecycle reads."""


def register_solution_lifecycle_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.solution_lifecycle_actions import (
        SolutionLifecycleActionInvalid,
        approve_location_solution_gate,
        approve_location_solution_retirement,
        propose_location_solution_funding,
        propose_location_solution_learning,
        propose_location_solution_retirement,
        record_location_solution_gate_evaluation,
        review_location_solution_experiment,
        submit_location_solution_funding,
        transition_location_solution_gate,
    )
    from services.gateway.solution_lifecycle_reads import (
        SolutionLifecycleReadInvalid,
        SolutionLifecycleResponseTooLarge,
        SolutionLifecycleReviewNotFound,
        get_location_solution_experiment_review,
        get_location_solution_funding_review_detail,
        get_location_solution_gate_review,
        get_location_solution_lifecycle_summary,
        get_location_solution_retirement_review_detail,
        list_location_solution_adoption,
        list_location_solution_experiments,
        list_location_solution_funding,
        list_location_solution_funding_review_queue,
        list_location_solution_funding_targets,
        list_location_solution_gates,
        list_location_solution_learning,
        list_location_solution_replications,
        list_location_solution_retirement_candidates,
        list_location_solution_retirement_review_queue,
        list_location_solution_retirements,
        list_location_solution_scale_gates,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/evaluations"
    )
    async def record_solution_gate_evaluation(
        request: Request, location_id: str, gate_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "passed", "observed", "evidence"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution gate evaluation fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                record_location_solution_gate_evaluation,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
                payload["request_id"],
                payload["passed"],
                payload["observed"],
                payload["evidence"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution gate not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution gate evaluation is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Solution gate changed; refresh and retry"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution gate evaluation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution gate evaluation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/review"
    )
    async def review_solution_gate_evaluation(
        request: Request, location_id: str, gate_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_gate_review,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Location-origin solution gate not found"},
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
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution gate review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution gate review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/approve"
    )
    async def approve_solution_gate(
        request: Request, location_id: str, gate_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution gate approval fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                approve_location_solution_gate,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active independent human reviewer with a current location review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution gate not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution gate approval request is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Gate is not eligible for approval; refresh and review the latest evaluation"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution gate approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution gate approval unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/transition"
    )
    async def transition_solution_gate(
        request: Request, location_id: str, gate_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {
            "request_id", "rationale", "evidence", "rollback_plan"
        }:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution gate transition fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_location_solution_gate,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
                payload["request_id"],
                payload["rationale"],
                payload["evidence"],
                payload["rollback_plan"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle transition access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle transition grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution gate not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution gate transition request is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Gate prerequisites changed; refresh and review the latest lifecycle state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution gate transition unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution gate transition unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

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

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/review"
    )
    async def review_solution_experiment_detail(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_experiment_review,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human with a current exact location review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Pending exact-location experiment review was not found"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution experiment review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution experiment review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/review"
    )
    async def submit_solution_experiment_review(
        request: Request, location_id: str, experiment_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "outcome", "primary_results", "secondary_results",
            "limitations", "evidence",
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution experiment review fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["outcome"],
                payload["primary_results"],
                payload["secondary_results"],
                payload["limitations"],
                payload["evidence"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human distinct from the experiment owner and protocol approver with a current location review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location solution experiment was not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution experiment review request is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Experiment is no longer eligible for review; refresh the lifecycle view"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution experiment result review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution experiment result review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/adoption")
    async def location_solution_lifecycle_adoption(
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
                list_location_solution_adoption,
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
                "Solution lifecycle adoption unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle adoption unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/scale-gates")
    async def location_solution_scale_gates(
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
                list_location_solution_scale_gates,
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
                "Solution scale-gate read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution scale-gate read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/replications")
    async def location_solution_replications(
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
                list_location_solution_replications,
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
                "Solution replication read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/learning")
    async def location_solution_learning(
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
                list_location_solution_learning,
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
                "Solution learning read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/learning"
    )
    async def propose_solution_learning(
        request: Request, location_id: str, replication_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "lesson_type", "finding", "recommended_action", "evidence"
        }
        optional_fields = {
            "confidence", "transferability", "affected_assumptions", "affected_metrics"
        }
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Learning proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_learning,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                payload["request_id"],
                payload["lesson_type"],
                payload["finding"],
                payload["recommended_action"],
                payload["evidence"],
                confidence=payload.get("confidence", "moderate"),
                transferability=payload.get("transferability", "unknown"),
                affected_assumptions=payload.get("affected_assumptions", []),
                affected_metrics=payload.get("affected_metrics", []),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Completed reviewed replication not found in this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Learning proposal input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Learning proposal conflicts with current state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/retirements")
    async def location_solution_retirements(
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
                list_location_solution_retirements,
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
                "Solution retirement read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/retirement-candidates")
    async def location_solution_retirement_candidates(
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
                list_location_solution_retirement_candidates,
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
                "Solution retirement candidate read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement candidate read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/retirements/review")
    async def location_solution_retirement_review_queue(
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
                list_location_solution_retirement_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
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
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/retirements/review/{retirement_id}"
    )
    async def location_solution_retirement_review_detail(
        request: Request, location_id: str, retirement_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_retirement_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                retirement_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Pending location-origin retirement review was not found"},
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
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Pending location-origin retirement review was not found"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/retirements"
    )
    async def propose_solution_retirement(
        request: Request, location_id: str, solution_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "retirement_type", "trigger_reason", "evidence_refs", "migration_plan"
        }
        allowed_fields = required_fields | {"replacement_solution_id"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(allowed_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Retirement proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_retirement,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["request_id"],
                payload["retirement_type"],
                payload["trigger_reason"],
                payload["evidence_refs"],
                payload["migration_plan"],
                payload.get("replacement_solution_id"),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Location solution not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Retirement proposal input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Retirement proposal conflicts with current state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/approve"
    )
    async def approve_solution_retirement(
        request: Request, location_id: str, retirement_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Retirement approval must contain only request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                approve_location_solution_retirement,
                request.state.operator_session.operator.operator_id,
                location_id,
                retirement_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Retirement not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Retirement approval request is invalid"}, headers=headers)
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(status_code=409, content={"error": "Retirement state conflicts with approval"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement approval unavailable"},
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

    @router.get("/operator/api/solution-lifecycle/{location_id}/funding/targets")
    async def location_solution_funding_targets(
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
                list_location_solution_funding_targets,
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
                    content={"error": "A current location solution-lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding targets unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding targets unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/funding/review")
    async def location_solution_funding_review_queue(
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
                list_location_solution_funding_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
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
                    content={"error": "A current exact-location solution lifecycle review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/review"
    )
    async def location_solution_funding_review_detail(
        request: Request, location_id: str, funding_case_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_funding_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(status_code=404, content={"error": "Funding review case not found"}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact-location solution lifecycle review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Funding review case not found"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/funding"
    )
    async def propose_solution_funding(
        request: Request, location_id: str, solution_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "capital_stage", "funding_instrument", "requested_amount",
            "minimum_viable_amount", "maximum_authorized_amount", "currency",
            "risk_adjusted_expected_value", "public_goods_value", "community_share",
            "downside_exposure", "rationale", "evidence", "tranches",
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution funding proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_funding,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["request_id"],
                payload["capital_stage"],
                payload["funding_instrument"],
                payload["requested_amount"],
                payload["minimum_viable_amount"],
                payload["maximum_authorized_amount"],
                payload["currency"],
                payload["risk_adjusted_expected_value"],
                payload["public_goods_value"],
                payload["community_share"],
                payload["downside_exposure"],
                payload["rationale"],
                payload["evidence"],
                payload["tranches"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human with a current location solution-lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution was not found"},
                    headers=headers,
                )
            if code in {"22023", "22003"}:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Solution funding proposal is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Funding proposal conflicts with an existing request"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/submit"
    )
    async def submit_solution_funding(
        request: Request, location_id: str, funding_case_id: str
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution funding submission fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_solution_funding,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle submit access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human with a current location solution-lifecycle submit grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Funding draft was not found for this operator and location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Solution funding submission is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Funding draft is no longer eligible for submission"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding submission unavailable"},
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
