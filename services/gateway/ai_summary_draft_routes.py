"""OIDC routes for authenticated AI-summary and synthesis draft requests."""


def register_ai_summary_draft_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.ai_summary_draft import (
        AiSummaryDraftInvalid,
        create_operator_ai_summary_draft,
    )
    from services.gateway.ai_summary_task_request import (
        AiSummaryTaskRequestInvalid,
        create_operator_ai_summary_task_request,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.post("/operator/api/ai-summaries/{location_id}/drafts")
    async def create_summary_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"summary_type", "request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Body must contain summary_type and request_id only"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_operator_ai_summary_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                summary_type=payload["summary_type"],
                request_id=payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified AI-summary draft access is required"},
                headers=headers,
            )
        except AiSummaryDraftInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except ValueError:
            return JSONResponse(
                status_code=409,
                content={"error": "Current reviewed location data is insufficient to generate this summary"},
                headers=headers,
            )
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location AI-summary draft grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The retry ID was reused with different draft content"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.ai_summary_draft").warning(
                "AI summary draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "AI summary draft generation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

    @router.post("/operator/api/ai-summaries/{location_id}/synthesis-requests")
    async def create_synthesis_request(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {
            "task_key", "summary_type", "request_id"
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Body must contain task_key, summary_type, and request_id only"
                },
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_operator_ai_summary_task_request,
                request.state.operator_session.operator.operator_id,
                location_id,
                task_key=payload["task_key"],
                summary_type=payload["summary_type"],
                request_id=payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified AI-summary draft access is required"},
                headers=headers,
            )
        except AiSummaryTaskRequestInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location AI-summary draft grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The retry ID was reused with different task intent"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.ai_summary_task_request").warning(
                "AI summary task request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "AI summary task request unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)
