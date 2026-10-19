"""OIDC route for location-scoped approved identity resolution."""


def register_stakeholder_identity_resolution_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.stakeholder_identity_resolution import (
        StakeholderIdentityResolutionInvalid,
        resolve_location_farmer_party_identity,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/stakeholder-identity/{location_id}/resolve/{source_profile_id}"
    )
    async def resolve_identity(request: Request, location_id: str, source_profile_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                resolve_location_farmer_party_identity,
                request.state.operator_session.operator.operator_id,
                location_id,
                source_profile_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified identity access is required"},
                headers=headers,
            )
        except StakeholderIdentityResolutionInvalid as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers=headers,
            )
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location resolution grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Identity resolution request is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.stakeholder_identity_resolution").warning(
                "Stakeholder identity resolution unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Stakeholder identity resolution unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Identity mapping is not available"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder({"location_id": location_id, **result}),
            headers=headers,
        )
