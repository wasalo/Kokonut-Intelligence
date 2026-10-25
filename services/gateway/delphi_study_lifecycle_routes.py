"""OIDC routes for Delphi study opening readiness and lifecycle transitions."""


def register_delphi_study_lifecycle_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_study_lifecycle import (
        DelphiStudyLifecycleInvalid,
        get_location_delphi_study_open_readiness,
        transition_location_delphi_study,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    async def transition(request: Request, location_id: str, study_id: str, action: str):
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
                content={"error": "A Delphi lifecycle request object is required"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi lifecycle request fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_location_delphi_study,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                action,
                request_id=payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": f"Tenant-qualified Delphi {action} access is required"},
                headers=headers,
            )
        except DelphiStudyLifecycleInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": f"A current location Delphi {action} grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The study is not ready for this transition or the request conflicts"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_lifecycle").warning(
                "Delphi study lifecycle request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi study lifecycle request unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=200, headers=headers)

    @router.get(
        "/operator/api/delphi/{location_id}/studies/{study_id}/open-readiness"
    )
    async def open_readiness(request: Request, location_id: str, study_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_delphi_study_open_readiness,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi open access is required"},
                headers=headers,
            )
        except DelphiStudyLifecycleInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location Delphi open grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_lifecycle").warning(
                "Delphi study readiness request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi study readiness is unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=200, headers=headers)

    @router.post("/operator/api/delphi/{location_id}/studies/{study_id}/open")
    async def open_study(request: Request, location_id: str, study_id: str):
        return await transition(request, location_id, study_id, "open")

    @router.post("/operator/api/delphi/{location_id}/studies/{study_id}/close")
    async def close_study(request: Request, location_id: str, study_id: str):
        return await transition(request, location_id, study_id, "close")
