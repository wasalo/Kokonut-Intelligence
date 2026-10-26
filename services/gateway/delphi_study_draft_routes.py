"""OIDC route for location-scoped Delphi study draft creation."""


def register_delphi_study_draft_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_study_drafts import (
        DelphiStudyDraftInvalid,
        create_location_delphi_study_draft,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.post("/operator/api/delphi/{location_id}/studies")
    async def create_study_draft(request: Request, location_id: str):
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
                content={"error": "A JSON Delphi study draft object is required"},
                headers=headers,
            )
        allowed_fields = {
            "request_id",
            "title",
            "description",
            "variation",
            "facilitator_type",
            "stopping_criteria",
        }
        if not isinstance(payload, dict) or set(payload) - allowed_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi study draft fields are invalid"},
                headers=headers,
            )
        if not {"request_id", "title"} <= set(payload):
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi study draft requires request_id and title"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_delphi_study_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id=payload["request_id"],
                title=payload["title"],
                description=payload.get("description"),
                variation=payload.get("variation", "real_time"),
                facilitator_type=payload.get("facilitator_type", "agent"),
                stopping_criteria=payload.get("stopping_criteria"),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi draft access is required"},
                headers=headers,
            )
        except DelphiStudyDraftInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location Delphi draft grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The Delphi study request is invalid or conflicts with an earlier request"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_draft").warning(
                "Delphi study draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi study draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)
