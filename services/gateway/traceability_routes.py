"""OIDC routes for private, location-scoped traceability reads."""

from uuid import UUID


def register_traceability_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query, Response
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from pydantic import ValidationError
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.traceability import (
        MAX_OFFSET,
        get_location_traceability_batch,
        list_location_traceability_batches,
    )
    from services.gateway.traceability_models import (
        TraceabilityBatchDetail,
        TraceabilityBatchPage,
    )

    @router.get(
        "/operator/api/traceability/{location_id}/batches",
        response_model=TraceabilityBatchPage,
    )
    async def traceability_batches(
        request: Request,
        response: Response,
        location_id: str,
        status: str | None = None,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=MAX_OFFSET),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                list_location_traceability_batches,
                request.state.operator_session.operator.operator_id,
                location_id,
                status=status,
                limit=limit,
                offset=offset,
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
            _log_failure("traceability batch list", exc)
            return _unavailable()
        try:
            validated = TraceabilityBatchPage.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.limit != limit
                or validated.offset != offset
                or len(validated.items) > limit
                or (
                    validated.has_more
                    and (len(validated.items) != limit or offset + limit > MAX_OFFSET)
                )
            ):
                raise ValueError("Traceability page does not match request")
        except (ValidationError, ValueError) as exc:
            _log_failure("traceability batch list response", exc)
            return JSONResponse(
                status_code=500,
                content={"error": "Traceability batch list unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            content=jsonable_encoder(validated.model_dump(mode="json")),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get(
        "/operator/api/traceability/{location_id}/batches/{batch_id}",
        response_model=TraceabilityBatchDetail,
    )
    async def traceability_batch(
        request: Request,
        response: Response,
        location_id: str,
        batch_id: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_traceability_batch,
                request.state.operator_session.operator.operator_id,
                location_id,
                batch_id,
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
            _log_failure("traceability batch detail", exc)
            return _unavailable()
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Traceability batch not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Cookie"
        return result


def _log_failure(operation: str, exc: Exception) -> None:
    from services.common.logging import get_logger

    get_logger("gateway.traceability").warning(
        "%s unavailable (%s)", operation, type(exc).__name__
    )


def _unavailable():
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=503,
        content={"error": "Traceability read unavailable"},
        headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
    )
