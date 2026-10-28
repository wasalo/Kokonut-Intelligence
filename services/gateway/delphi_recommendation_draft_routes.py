"""OIDC routes for location-scoped Delphi facilitator draft creation."""


def register_delphi_recommendation_draft_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_recommendation_drafts import (
        DelphiDraftInvalid,
        create_location_delphi_recommendation_draft,
        list_location_delphi_draftable_studies,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location Delphi draft grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "Drafts require an open or closed Delphi study"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi draft request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_recommendation_drafts").warning(
            "Delphi recommendation draft unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi recommendation draft unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.get("/operator/api/delphi/{location_id}/draft-studies")
    async def list_draftable_studies(
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
                list_location_delphi_draftable_studies,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi draft access is required"},
                headers=headers,
            )
        except DelphiDraftInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/delphi/{location_id}/studies/{study_id}/recommendation-drafts"
    )
    async def create_recommendation_draft(
        request: Request,
        location_id: str,
        study_id: str,
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
                content={"error": "A JSON recommendation draft object is required"},
                headers=headers,
            )
        if (
            not isinstance(payload, dict)
            or set(payload) != {"request_id", "summary", "recommendation_text"}
            or not isinstance(payload.get("request_id"), str)
            or not isinstance(payload.get("recommendation_text"), str)
            or (payload.get("summary") is not None and not isinstance(payload.get("summary"), str))
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Recommendation draft fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_delphi_recommendation_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                request_id=payload["request_id"],
                summary=payload["summary"],
                recommendation_text=payload["recommendation_text"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi draft access is required"},
                headers=headers,
            )
        except DelphiDraftInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
