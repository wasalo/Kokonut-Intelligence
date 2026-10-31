"""OIDC route registration for location-scoped yield summaries."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _YieldSummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class YieldUnitSummary(_YieldSummaryModel):
    yield_unit: str | None
    observations: int = Field(ge=0)
    avg_yield: float | None
    total_yield: float | None


class YieldCropSummary(_YieldSummaryModel):
    crop_name: str | None
    yield_unit: str | None
    observations: int = Field(ge=0)
    avg_yield: float | None
    min_yield: float | None
    max_yield: float | None
    stddev_yield: float | None
    total_production: float | None


class RecentHarvestSummary(_YieldSummaryModel):
    harvest_date: date | None
    crop_name: str | None
    yield_amount: float | None
    yield_unit: str | None
    area_ha: float | None
    total_yield: float | None
    grade: str | None


class YieldSummaryResponse(_YieldSummaryModel):
    location_id: UUID
    total_observations: int = Field(ge=0)
    first_harvest: date | None
    last_harvest: date | None
    totals_by_yield_unit: list[YieldUnitSummary]
    crops: list[YieldCropSummary]
    recent_harvests: list[RecentHarvestSummary]


def register_yield_monitoring_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.yield_monitoring import get_location_yield_summary

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/yield-monitoring/{location_id}/summary",
        response_model=YieldSummaryResponse,
    )
    async def yield_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            summary = await run_in_threadpool(
                get_location_yield_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers=headers,
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.yield_monitoring").warning(
                "Yield summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Yield summary unavailable"},
                headers={
                    "Retry-After": "30",
                    **headers,
                },
            )
        try:
            validated = YieldSummaryResponse.model_validate(summary)
        except ValidationError as exc:
            from services.common.logging import get_logger

            get_logger("gateway.yield_monitoring").warning(
                "Yield summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Yield summary unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers=headers,
        )
