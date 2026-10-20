"""OIDC routes for location-scoped solution lifecycle reads."""


def register_solution_lifecycle_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.solution_lifecycle_actions import (
        SolutionLifecycleActionInvalid,
        activate_location_solution_replication,
        analyze_location_solution_experiment,
        apply_location_solution_learning,
        approve_location_solution_experiment_protocol,
        approve_location_solution_funding,
        approve_location_solution_funding_tranche,
        approve_location_solution_gate,
        approve_location_solution_retirement,
        complete_location_solution_experiment,
        create_location_solution,
        create_location_solution_experiment,
        create_location_solution_gate,
        propose_location_solution_funding,
        propose_location_solution_learning,
        propose_location_solution_replication,
        propose_location_solution_replication_completion,
        propose_location_solution_retirement,
        record_location_solution_experiment_observation,
        record_location_solution_gate_evaluation,
        review_location_solution_experiment,
        review_location_solution_learning,
        review_location_solution_replication,
        review_location_solution_replication_completion,
        review_location_solution_scale_gate_assessment,
        start_location_solution_experiment,
        submit_location_solution_experiment_protocol,
        submit_location_solution_funding,
        submit_location_solution_scale_gate_assessment,
        transition_location_solution_gate,
        transition_location_solution_retirement,
        transition_location_solution_stage,
    )
    from services.gateway.solution_lifecycle_reads import (
        SolutionLifecycleReadInvalid,
        SolutionLifecycleRecordNotFound,
        SolutionLifecycleResponseTooLarge,
        SolutionLifecycleReviewNotFound,
        get_location_solution_adoption_event_summary,
        get_location_solution_experiment_protocol_review,
        get_location_solution_experiment_review,
        get_location_solution_funding_review_detail,
        get_location_solution_funding_tranche_review_detail,
        get_location_solution_gate_review,
        get_location_solution_learning_review_detail,
        get_location_solution_lifecycle_summary,
        get_location_solution_replication_completion_review_detail,
        get_location_solution_replication_review_detail,
        get_location_solution_retirement_review_detail,
        get_location_solution_scale_gate_review_detail,
        list_location_solution_adoption,
        list_location_solution_experiments,
        list_location_solution_funding,
        list_location_solution_funding_review_queue,
        list_location_solution_funding_targets,
        list_location_solution_gates,
        list_location_solution_learning,
        list_location_solution_learning_applications,
        list_location_solution_learning_review_queue,
        list_location_solution_replication_completion_review_queue,
        list_location_solution_replication_review_queue,
        list_location_solution_replications,
        list_location_solution_retirement_candidates,
        list_location_solution_retirement_review_queue,
        list_location_solution_retirements,
        list_location_solution_scale_gate_assessment_targets,
        list_location_solution_scale_gate_review_queue,
        list_location_solution_scale_gates,
        list_location_solution_stage_transition_targets,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.post("/operator/api/solution-lifecycle/{location_id}/solutions")
    async def create_solution(request: Request, location_id: str):
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
            "request_id", "canonical_key", "name", "solution_type",
            "problem_statement", "rationale", "evidence", "acknowledged",
        }
        optional_fields = {
            "theory_of_change", "baseline_alternative", "risk_class", "reversibility",
        }
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Location solution fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_solution,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload["request_id"],
                payload["canonical_key"],
                payload["name"],
                payload["solution_type"],
                payload["problem_statement"],
                payload["rationale"],
                payload["evidence"],
                theory_of_change=payload.get("theory_of_change"),
                baseline_alternative=payload.get("baseline_alternative"),
                risk_class=payload.get("risk_class", "medium"),
                reversibility=payload.get("reversibility", "medium"),
                acknowledged=payload["acknowledged"],
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
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Location solution input is invalid"}, headers=headers)
            if code == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Solution key or request identifier already exists; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Location solution creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Location solution creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/gates"
    )
    async def create_solution_gate(request: Request, location_id: str, solution_id: str):
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
            "request_id", "to_stage", "criterion", "required_experiment_count",
            "acknowledged",
        }
        optional_fields = {"required_evidence_maturity"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Location solution gate fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_solution_gate,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["request_id"],
                payload["to_stage"],
                payload["criterion"],
                payload.get("required_evidence_maturity"),
                payload["required_experiment_count"],
                payload["acknowledged"],
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
                    content={"error": "Location-origin active solution not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Location solution gate input is invalid"},
                    headers=headers,
                )
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "A gate already exists or the solution stage changed; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Location solution gate creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Location solution gate creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/experiments"
    )
    async def create_solution_experiment(request: Request, location_id: str, solution_id: str):
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
        required_fields = {"request_id", "protocol", "acknowledged"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment protocol fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["request_id"],
                payload["protocol"],
                payload["acknowledged"],
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
                    content={"error": "Location-origin solution not found"},
                    headers=headers,
                )
            if code == "55000":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The solution is not active and experiment-ready"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment protocol input is invalid"},
                    headers=headers,
                )
            if code == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Experiment request identifier already exists; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Location solution experiment creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Location solution experiment creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/submit"
    )
    async def submit_solution_experiment_protocol(
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
        required_fields = {"request_id", "acknowledged"}
        if (
            not isinstance(payload, dict)
            or set(payload) != required_fields
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment submission fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_solution_experiment_protocol,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
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
                    content={"error": "An active location submit grant and protocol owner identity are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location experiment protocol not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment submission input is invalid"},
                    headers=headers,
                )
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The experiment is no longer an eligible draft; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment protocol submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment protocol submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

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

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/stage-transition"
    )
    async def transition_solution_stage(
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
            "request_id", "expected_from_stage", "to_stage", "rationale",
            "evidence", "rollback_plan", "acknowledged",
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution stage transition fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_location_solution_stage,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["expected_from_stage"],
                payload["to_stage"],
                payload["request_id"],
                payload["rationale"],
                payload["evidence"],
                payload["rollback_plan"],
                payload["acknowledged"],
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
                    content={"error": "Location-origin solution not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution stage transition request is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Solution stage changed or transition conflicts with lifecycle prerequisites; refresh and retry"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution stage transition unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution stage transition unavailable"},
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
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/protocol-review"
    )
    async def review_solution_experiment_protocol_detail(
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
                get_location_solution_experiment_protocol_review,
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
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Submitted exact-location experiment protocol not found"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Submitted exact-location experiment protocol not found"},
                    headers=headers,
                )
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment protocol review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment protocol review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/protocol-review"
    )
    async def approve_solution_experiment_protocol(
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
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Protocol approval fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                approve_location_solution_experiment_protocol,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["acknowledged"],
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
                    content={"error": "An active review grant and independent human reviewer are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Submitted exact-location experiment protocol not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Protocol approval request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The protocol is no longer eligible for approval; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment protocol approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment protocol approval unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/start"
    )
    async def start_solution_experiment(
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
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment start fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                start_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["acknowledged"],
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
                    content={"error": "An active transition grant and human identity are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location experiment not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment start acknowledgement is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The experiment is not eligible to start; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment start unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment start unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/observations"
    )
    async def record_solution_experiment_observation_route(
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
            "request_id", "metric_key", "value", "arm", "adverse_event",
            "evidence", "acknowledged",
        }
        optional_fields = {"unit_ref", "participant_link_id"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or set(payload) - required_fields - optional_fields
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment observation fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                record_location_solution_experiment_observation,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["metric_key"],
                payload["value"],
                payload["arm"],
                payload.get("unit_ref"),
                payload["adverse_event"],
                payload["evidence"],
                payload.get("participant_link_id"),
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle collection access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active exact-location collection grant and current consent are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location active experiment not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment observation input is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Experiment observation is not eligible; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment observation capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment observation capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/analyze"
    )
    async def analyze_solution_experiment_route(
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
        required_fields = {"request_id", "metric_key", "acknowledged"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment analysis fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                analyze_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["metric_key"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle analysis access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active exact-location analysis grant and current observation consent are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location active experiment not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment analysis input or protocol settings are invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Experiment analysis is not eligible; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment analysis unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment analysis unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/complete"
    )
    async def complete_solution_experiment_route(
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
        required_fields = {"request_id", "acknowledged"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment completion fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                complete_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["acknowledged"],
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
                    content={"error": "Active exact-location transition and analyze grants are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location active experiment not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment completion request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Experiment is not at a current approved stopping boundary; refresh analysis and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment completion unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment completion unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

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

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/adoption/{program_id}/events"
    )
    async def location_solution_lifecycle_adoption_event_summary(
        request: Request, location_id: str, program_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_adoption_event_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
                program_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleRecordNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Exact-location adoption program was not found"},
                headers=headers,
            )
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location adoption program was not found"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption event summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution adoption event summary unavailable"},
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

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/scale-gates/assessment-targets"
    )
    async def location_solution_scale_gate_assessment_targets(
        request: Request,
        location_id: str,
        limit: str = "25",
        offset: str = "0",
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                list_location_solution_scale_gate_assessment_targets,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified assessment access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location create grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate assessment targets unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate assessment targets unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/scale-gates/{gate_id}/evaluations"
    )
    async def submit_solution_scale_gate_assessment(
        request: Request, location_id: str, gate_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "measured_value", "sample_size", "reported_pass",
            "evidence_refs", "acknowledged",
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(status_code=400, content={"error": "Scale-gate assessment fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                submit_location_solution_scale_gate_assessment,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
                payload["request_id"],
                payload["measured_value"],
                payload["sample_size"],
                payload["reported_pass"],
                payload["evidence_refs"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified scale-gate assessment access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location create grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Scale gate not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Scale-gate assessment input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Scale gate already has a pending assessment or the request conflicts"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate assessment unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate assessment unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/scale-gates/review")
    async def location_solution_scale_gate_review_queue(
        request: Request,
        location_id: str,
        limit: str = "25",
        offset: str = "0",
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                list_location_solution_scale_gate_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified scale-gate review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate review queue unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/scale-gates/review/{assessment_id}"
    )
    async def location_solution_scale_gate_review_detail(
        request: Request, location_id: str, assessment_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_solution_scale_gate_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                assessment_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified scale-gate review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate review detail unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/scale-gates/review/{assessment_id}"
    )
    async def review_solution_scale_gate_assessment(
        request: Request, location_id: str, assessment_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "decision", "review_reason", "acknowledged"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(status_code=400, content={"error": "Scale-gate review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_scale_gate_assessment,
                request.state.operator_session.operator.operator_id,
                location_id,
                assessment_id,
                payload["request_id"],
                payload["decision"],
                payload["review_reason"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified scale-gate review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An active independent human location review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Pending scale-gate assessment not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Scale-gate review input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Scale-gate assessment was already reviewed or the request conflicts"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate review unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

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

    @router.get("/operator/api/solution-lifecycle/{location_id}/replications/review")
    async def location_solution_replication_review_queue(
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
                list_location_solution_replication_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/review")
    async def location_solution_replication_review_detail(
        request: Request, location_id: str, replication_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_replication_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/review")
    async def review_solution_replication(request: Request, location_id: str, replication_id: str):
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
        required_fields = {"request_id", "decision", "acknowledged"}
        optional_fields = {"review_reason"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(status_code=400, content={"error": "Replication review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_replication,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                payload["request_id"],
                payload["decision"],
                payload.get("review_reason"),
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An independent human with an active location review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Pending attributed replication proposal not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Replication review input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Replication proposal has already been reviewed or changed"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/replications/completion-review"
    )
    async def location_solution_replication_completion_review_queue(
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
                list_location_solution_replication_completion_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Replication completion review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Replication completion review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/completion-proposals/{proposal_id}/review"
    )
    async def location_solution_replication_completion_review_detail(
        request: Request,
        location_id: str,
        replication_id: str,
        proposal_id: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_replication_completion_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                proposal_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Replication completion review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Replication completion review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/completion-proposals/{proposal_id}/review"
    )
    async def review_solution_replication_completion(
        request: Request,
        location_id: str,
        replication_id: str,
        proposal_id: str,
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
        required_fields = {"request_id", "decision", "acknowledged"}
        optional_fields = {"review_reason"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(status_code=400, content={"error": "Completion review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_replication_completion,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                proposal_id,
                payload["request_id"],
                payload["decision"],
                payload.get("review_reason"),
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An independent human with an active location review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Pending completion report with current source lineage not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Completion review input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Completion report has already been reviewed or changed"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Replication completion review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Replication completion review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/start"
    )
    async def start_solution_replication(
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
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Replication activation fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                activate_location_solution_replication,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                payload["request_id"],
                payload["acknowledged"],
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
                    content={"error": "An active human with a current location transition grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Independently approved replication not found for this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Replication activation input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Replication cannot be started in its current state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication activation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication activation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/completion-proposals"
    )
    async def propose_solution_replication_completion(
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
            "request_id", "outcome", "evidence_maturity", "outcome_summary", "evidence", "acknowledged"
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Replication completion proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_replication_completion,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                payload["request_id"],
                payload["outcome"],
                payload["evidence_maturity"],
                payload["outcome_summary"],
                payload["evidence"],
                acknowledged=payload["acknowledged"],
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
                    content={"error": "An active human with a current location submit grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Started replication not found for this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Replication completion proposal is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001", "55P03"}:
                return JSONResponse(status_code=409, content={"error": "A completion proposal is already pending or this replication changed"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication completion proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication completion proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

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

    @router.get("/operator/api/solution-lifecycle/{location_id}/learning/application")
    async def location_solution_learning_application_queue(
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
                list_location_solution_learning_applications,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified application access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location apply grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning application queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning application queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/apply"
    )
    async def apply_solution_learning(
        request: Request, location_id: str, learning_record_id: str
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
        required_fields = {"request_id", "applied_to_version", "acknowledged"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Learning application fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                apply_location_solution_learning,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_record_id,
                payload["request_id"],
                payload["applied_to_version"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified application access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location apply grant distinct from the reviewer is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Accepted learning with current source lineage not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Learning application input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Learning record is already applied or its application request conflicts"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning application unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning application unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/learning/review")
    async def location_solution_learning_review_queue(
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
                list_location_solution_learning_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/review"
    )
    async def location_solution_learning_review_detail(
        request: Request, location_id: str, learning_record_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_learning_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_record_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/review"
    )
    async def review_solution_learning(
        request: Request, location_id: str, learning_record_id: str
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
        required_fields = {"request_id", "decision", "acknowledged"}
        optional_fields = {"review_reason"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(status_code=400, content={"error": "Learning review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_learning,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_record_id,
                payload["request_id"],
                payload["decision"],
                payload.get("review_reason"),
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An independent human with an active location review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Pending learning proposal with current source lineage not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Learning review input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Learning proposal has already been reviewed or changed"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post("/operator/api/solution-lifecycle/{location_id}/replications")
    async def propose_solution_replication(request: Request, location_id: str):
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
            "request_id", "source_experiment_id", "target_context", "replication_protocol"
        }
        optional_fields = {"adaptation_required"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Replication proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_replication,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload["source_experiment_id"],
                payload["request_id"],
                payload["target_context"],
                payload.get("adaptation_required"),
                payload["replication_protocol"],
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
                    content={"error": "Validated source experiment not found for this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Replication proposal input is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Replication proposal conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication proposal unavailable"},
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

    async def _transition_solution_retirement(
        request: Request, location_id: str, retirement_id: str, action: str
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
            "request_id", "note", "evidence_refs", "effective_at", "acknowledged"
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Retirement transition fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_location_solution_retirement,
                request.state.operator_session.operator.operator_id,
                location_id,
                retirement_id,
                payload["request_id"],
                action,
                payload["note"],
                payload["evidence_refs"],
                payload["effective_at"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution retirement transition access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current active-human location transition or review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Retirement not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Retirement transition input is invalid"}, headers=headers)
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(status_code=409, content={"error": "Retirement is not eligible for this transition"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement transition unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement transition unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/migration"
    )
    async def begin_solution_retirement_migration(
        request: Request, location_id: str, retirement_id: str
    ):
        return await _transition_solution_retirement(
            request, location_id, retirement_id, "migration_started"
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/sunset"
    )
    async def sunset_location_solution_retirement(
        request: Request, location_id: str, retirement_id: str
    ):
        return await _transition_solution_retirement(
            request, location_id, retirement_id, "sunset"
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/post-retirement-review"
    )
    async def complete_location_solution_retirement_review(
        request: Request, location_id: str, retirement_id: str
    ):
        return await _transition_solution_retirement(
            request, location_id, retirement_id, "post_retirement_review"
        )

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

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/tranches/{tranche_id}/review"
    )
    async def location_solution_funding_tranche_review_detail(
        request: Request, location_id: str, funding_case_id: str, tranche_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_funding_tranche_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
                tranche_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(status_code=404, content={"error": "Funding tranche was not found"}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current exact-location funding review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Funding tranche was not found"}, headers=headers)
            if code == "54000":
                return JSONResponse(status_code=413, content={"error": "Funding tranche review terms exceed the allowed size"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding tranche review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution funding tranche review unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/approve"
    )
    async def approve_solution_funding(
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
                content={"error": "Solution funding approval fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                approve_location_solution_funding,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
                payload["request_id"],
                payload["acknowledged"],
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
                    content={"error": "An active independent human with a current location review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Submitted funding case was not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution funding approval is invalid"}, headers=headers)
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Funding case is no longer eligible for approval"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding approval unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/tranches/{tranche_id}/approve"
    )
    async def approve_solution_funding_tranche_route(
        request: Request, location_id: str, funding_case_id: str, tranche_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(status_code=400, content={"error": "Solution tranche approval fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                approve_location_solution_funding_tranche,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
                tranche_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An active independent human distinct from the submitter and case approver is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Funding tranche was not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution funding tranche approval is invalid"}, headers=headers)
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(status_code=409, content={"error": "Funding case or tranche is no longer eligible for approval"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding tranche approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution funding tranche approval unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

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

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/stage-transition-targets"
    )
    async def location_solution_stage_transition_targets(
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
                list_location_solution_stage_transition_targets,
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
                "Solution stage-transition targets unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution stage-transition targets unavailable"},
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
