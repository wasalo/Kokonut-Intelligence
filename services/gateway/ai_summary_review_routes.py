"""OIDC routes for location-scoped human review of AI summary drafts."""


def register_ai_summary_review_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.ai_summary_review import (
        AiSummaryReviewInvalid,
        decide_location_ai_summary_review,
        list_location_ai_summary_reviews,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location AI-summary review grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "The AI summary is not currently reviewable"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "AI-summary review request is invalid"},
                headers=headers,
            )
        if code == "23505":
            return JSONResponse(
                status_code=409,
                content={"error": "The AI summary already has a review decision"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.ai_summary_review").warning(
            "AI summary review unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "AI summary review unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.get("/operator/api/ai-summaries/{location_id}/reviews")
    async def list_summary_reviews(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_ai_summary_reviews,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified AI-summary review access is required"},
                headers=headers,
            )
        except AiSummaryReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/ai-summaries/{location_id}/reviews/{summary_id}/decision"
    )
    async def decide_summary_review(
        request: Request,
        location_id: str,
        summary_id: str,
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
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {
            "decision",
            "request_id",
            "reason_code",
        }:
            return JSONResponse(
                status_code=400,
                content={"error": "Body must contain decision, request_id, and reason_code only"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                decide_location_ai_summary_review,
                request.state.operator_session.operator.operator_id,
                location_id,
                summary_id,
                decision=payload["decision"],
                request_id=payload["request_id"],
                reason_code=payload["reason_code"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified AI-summary review access is required"},
                headers=headers,
            )
        except AiSummaryReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
