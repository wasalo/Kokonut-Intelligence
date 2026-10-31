"""OIDC route registration for location-scoped energy summaries."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_SOURCE_TYPE = Literal[
    "grid", "diesel_generator", "solar", "wind", "biogas", "biomass", "battery"
]
_RENEWABLE_TYPE = Literal["solar_pv", "solar_thermal", "wind", "biogas", "micro_hydro"]


class _EnergyResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EnergyReadingGroup(_EnergyResponseModel):
    reading_type: Literal["consumption", "production"]
    source_type: _SOURCE_TYPE
    activity_type: Literal[
        "irrigation", "processing", "storage", "lighting", "pump", "other", "unspecified"
    ]
    reading_count: int = Field(ge=0, strict=True)
    total_kwh: float
    first_reading_date: str | None
    last_reading_date: str | None


class EnergyEmissionsBySource(_EnergyResponseModel):
    source_type: _SOURCE_TYPE
    consumption_kwh: float
    emission_factor_kg_co2e_per_kwh: float = Field(ge=0)
    estimated_emissions_kg_co2e: float = Field(ge=0)


class EnergyRenewableByType(_EnergyResponseModel):
    renewable_type: _RENEWABLE_TYPE
    source_count: int = Field(ge=0, strict=True)
    capacity_kw: float
    annual_generation_kwh: float
    registered_carbon_offset_kg: float


class EnergyTrendPoint(_EnergyResponseModel):
    reading_date: str
    consumption_kwh: float
    production_kwh: float


class ReviewedEnergyEfficiencyPoint(_EnergyResponseModel):
    log_date: str
    period: Literal["daily"]
    total_consumption_kwh: float | None
    total_production_kwh: float | None
    net_energy_kwh: float | None
    renewable_pct: float | None
    carbon_intensity_kg_kwh: float | None


class ActiveEnergySourceType(_EnergyResponseModel):
    source_type: _SOURCE_TYPE
    source_count: int = Field(ge=0, strict=True)
    capacity_kw: float


class EnergyCostByCurrency(_EnergyResponseModel):
    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    total_cost: float
    costed_kwh: float
    effective_cost_per_kwh: float | None
    reading_count: int = Field(ge=0, strict=True)


class ComparableEnergyCost(_EnergyResponseModel):
    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    total_cost: float
    effective_cost_per_kwh: float | None


class EnergyCostSummary(_EnergyResponseModel):
    period_days: Literal[30]
    by_currency: list[EnergyCostByCurrency] = Field(max_length=26**3)
    unclassified_cost_reading_count: int = Field(ge=0, strict=True)
    comparable_total: ComparableEnergyCost | None


class LegacyCarbonEstimate(_EnergyResponseModel):
    model: Literal["legacy_source_type_factors_v1"]
    total_emissions_kg_co2e: float
    intensity_kg_co2e_per_kwh: float
    monthly_carbon_offset_kg: float
    net_monthly_emissions_kg: float
    by_source_type: list[EnergyEmissionsBySource] = Field(max_length=7)


class RegisteredRenewables(_EnergyResponseModel):
    period_days: Literal[365]
    active_sources: int = Field(ge=0, strict=True)
    total_capacity_kw: float
    annual_generation_kwh: float
    registered_carbon_offset_kg: float
    annual_verified_consumption_kwh: float
    legacy_generation_coverage_pct: float = Field(ge=0, le=100)
    by_type: list[EnergyRenewableByType] = Field(max_length=5)


class EnergyDashboardCalculations(_EnergyResponseModel):
    period_days: Literal[30]
    total_consumption_kwh: float
    total_production_kwh: float
    net_energy_kwh: float
    renewable_consumption_kwh: float
    renewable_share_pct: float = Field(ge=0, le=100)
    legacy_carbon_estimate: LegacyCarbonEstimate
    registered_renewables: RegisteredRenewables
    trend_7d: list[EnergyTrendPoint] = Field(max_length=8)
    reviewed_efficiency_history: list[ReviewedEnergyEfficiencyPoint] = Field(max_length=12)
    active_sources_by_type: list[ActiveEnergySourceType] = Field(max_length=7)
    energy_costs: EnergyCostSummary


class EnergyMonitoringSummaryResponse(_EnergyResponseModel):
    location_id: UUID
    unit: Literal["kWh"]
    verified_reading_count: int = Field(ge=0, strict=True)
    groups: list[EnergyReadingGroup] = Field(max_length=98)
    dashboard_calculations: EnergyDashboardCalculations


def register_energy_monitoring_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.energy_monitoring import get_location_energy_summary

    @router.get(
        "/operator/api/energy/{location_id}/summary",
        response_model=EnergyMonitoringSummaryResponse,
    )
    async def energy_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_energy_summary,
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

            get_logger("gateway.energy").warning(
                "Energy summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Energy summary unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )
        try:
            validated = EnergyMonitoringSummaryResponse.model_validate(result)
            if validated.location_id != UUID(location_id):
                raise ValueError("Energy summary location does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.energy").warning(
                "Energy summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Energy summary unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
