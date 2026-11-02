"""OIDC route registration for location-scoped landscape summaries."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _LandscapeResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class LandscapeHabitatAggregate(_LandscapeResponseModel):
    habitat_type: Literal[
        "wetland", "riparian", "forest_patch", "grassland", "hedgerow",
        "orchard", "agroforestry", "other",
    ]
    status: Literal["active", "inactive", "degraded", "restored", "archived"]
    biodiversity_value: Literal["low", "medium", "high", "critical"] | None
    record_count: int = Field(ge=1, strict=True)
    total_area_ha: float | None


class LandscapeCorridorAggregate(_LandscapeResponseModel):
    condition: Literal["excellent", "good", "fair", "poor", "degraded"] | None
    status: Literal["active", "inactive", "restored", "degraded", "archived"]
    record_count: int = Field(ge=1, strict=True)
    total_length_m: float | None
    mean_width_m: float | None


class LandscapeHedgerowAggregate(_LandscapeResponseModel):
    condition: Literal["excellent", "good", "fair", "poor"] | None
    status: Literal["active", "inactive", "maintained", "needs_attention", "removed"]
    record_count: int = Field(ge=1, strict=True)
    total_length_m: float | None
    mean_height_m: float | None


class LandscapeBufferCheckAggregate(_LandscapeResponseModel):
    compliant: bool | None
    erosion_observed: bool | None
    record_count: int = Field(ge=1, strict=True)
    first_check_date: date | None
    last_check_date: date | None


class VerifiedLandscapeAssessments(_LandscapeResponseModel):
    assessment_count: int = Field(ge=0, strict=True)
    mean_species_richness: float | None
    mean_shannon_index: float | None
    mean_habitat_diversity_index: float | None
    mean_connectivity_score: float | None
    mean_overall_score: float | None
    first_assessment_date: date | None
    last_assessment_date: date | None


class ActiveHabitatDashboard(_LandscapeResponseModel):
    zone_count: int = Field(ge=0, strict=True)
    total_area_ha: float
    critical_habitats: int = Field(ge=0, strict=True)
    high_value_habitats: int = Field(ge=0, strict=True)


class ActiveCorridorDashboard(_LandscapeResponseModel):
    corridor_count: int = Field(ge=0, strict=True)
    healthy_corridors: int = Field(ge=0, strict=True)
    total_length_m: float
    mean_width_m: float


class VerifiedBufferDashboard(_LandscapeResponseModel):
    total_checks: int = Field(ge=0, strict=True)
    compliant_checks: int = Field(ge=0, strict=True)
    compliance_pct: float = Field(ge=0, le=100)
    erosion_incidents: int = Field(ge=0, strict=True)


class LandscapeDashboardCalculations(_LandscapeResponseModel):
    active_habitats: ActiveHabitatDashboard
    active_corridors: ActiveCorridorDashboard
    verified_buffer_checks: VerifiedBufferDashboard
    # This is a legacy ratio, not a normalized percentage: healthy corridors
    # and active habitats count different record types and can exceed 100.
    legacy_connectivity_ratio_pct: float


class LandscapeSummaryResponse(_LandscapeResponseModel):
    location_id: UUID
    habitats: list[LandscapeHabitatAggregate] = Field(max_length=200)
    corridors: list[LandscapeCorridorAggregate] = Field(max_length=30)
    hedgerows: list[LandscapeHedgerowAggregate] = Field(max_length=25)
    verified_buffer_checks: list[LandscapeBufferCheckAggregate] = Field(max_length=9)
    verified_assessments: VerifiedLandscapeAssessments
    dashboard_calculations: LandscapeDashboardCalculations


def register_landscape_conservation_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.landscape_conservation_mutation_routes import (
        register_landscape_conservation_mutation_routes,
    )
    from services.gateway.landscape_conservation_reads import get_location_landscape_summary

    @router.get(
        "/operator/api/landscape/{location_id}/summary",
        response_model=LandscapeSummaryResponse,
    )
    async def landscape_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_landscape_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
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

            get_logger("gateway.landscape").warning(
                "Landscape summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Landscape summary unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            validated = LandscapeSummaryResponse.model_validate(result)
            if validated.location_id != UUID(location_id):
                raise ValueError("Landscape summary location does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.landscape").warning(
                "Landscape summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Landscape summary unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    register_landscape_conservation_mutation_routes(
        router, provider, run_in_threadpool, psycopg2
    )
