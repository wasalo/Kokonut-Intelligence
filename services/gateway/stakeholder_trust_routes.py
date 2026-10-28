"""OIDC route for location-scoped, reviewed stakeholder trust evidence."""


def register_stakeholder_trust_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.stakeholder_trust import (
        StakeholderTrustInvalid,
        list_location_identity_trust_evidence,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/stakeholder-trust/{location_id}/parties/{party_id}/identity-evidence"
    )
    async def location_identity_trust_evidence(
        request: Request,
        location_id: str,
        party_id: str,
        limit: int = Query(default=50, ge=1, le=50),
        cursor_reviewed_at: str | None = None,
        cursor_evidence_id: str | None = None,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_identity_trust_evidence,
                request.state.operator_session.operator.operator_id,
                location_id,
                party_id,
                limit=limit,
                cursor_reviewed_at=cursor_reviewed_at,
                cursor_evidence_id=cursor_evidence_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trust access is required"},
                headers=headers,
            )
        except StakeholderTrustInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location trust grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Trust evidence request is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.stakeholder_trust").warning(
                "Stakeholder trust request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Stakeholder trust service unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)
