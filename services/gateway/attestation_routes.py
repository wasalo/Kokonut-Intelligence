"""OIDC route registration for privacy-preserving location attestations."""


def register_attestation_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.attestation_models import LocationAttestationsResponse
    from services.gateway.attestations import list_location_attestations

    @router.get(
        "/operator/api/attestations/{location_id}",
        response_model=LocationAttestationsResponse,
    )
    async def location_attestations(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            rows = await run_in_threadpool(
                list_location_attestations,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.attestations").warning(
                "Location attestation read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Location attestation read unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )

        response = LocationAttestationsResponse(data=rows, location_id=location_id)
        return JSONResponse(
            response.model_dump(mode="json"),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
