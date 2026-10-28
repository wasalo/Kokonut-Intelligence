"""OIDC routes for location-scoped private Delphi minority-report review."""


def register_delphi_minority_review_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_minority_review import (
        DelphiMinorityReviewInvalid,
        decide_location_delphi_minority_report,
        list_location_delphi_minority_reports,
    )

    headers = {"Cache-Control": "no-store", "Pragma": "no-cache", "Vary": "Cookie"}

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location Delphi review grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "The minority report is not currently reviewable"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi minority-report review request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_minority_review").warning(
            "Delphi minority-report review unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi minority-report review unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.get("/operator/api/delphi/{location_id}/minority-reports")
    async def list_minority_reports(
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
                list_location_delphi_minority_reports,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi review access is required"},
                headers=headers,
            )
        except DelphiMinorityReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/delphi/{location_id}/minority-reports/{report_id}/decision"
    )
    async def decide_minority_report(request: Request, location_id: str, report_id: str):
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
                content={"error": "A JSON decision object is required"},
                headers=headers,
            )
        expected = {"decision", "request_id", "reason_code"}
        if (
            not isinstance(payload, dict)
            or set(payload) != expected
            or not all(isinstance(payload.get(key), str) for key in expected)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Decision fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                decide_location_delphi_minority_report,
                request.state.operator_session.operator.operator_id,
                location_id,
                report_id,
                decision=payload["decision"],
                request_id=payload["request_id"],
                reason_code=payload["reason_code"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi review access is required"},
                headers=headers,
            )
        except DelphiMinorityReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
