"""OIDC route registration for location-scoped crop simulation summaries."""

from datetime import date
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator


class _CropSimulationResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CropSimulationRunResponse(_CropSimulationResponseModel):
    twin_id: UUID
    twin_name: str = Field(max_length=300)
    run_id: UUID
    started_at: AwareDatetime | None
    completed_at: AwareDatetime | None
    duration_ms: int | None = Field(strict=True)
    final_yield: float | None = Field(strict=True)
    final_yield_unit: str | None = Field(max_length=50)
    total_water_mm: float | None = Field(strict=True)
    total_nitrogen_kg: float | None = Field(strict=True)
    avg_soil_carbon_pct: float | None = Field(strict=True)


class CropSimulationStateResponse(_CropSimulationResponseModel):
    day_number: int = Field(strict=True)
    state_date: date
    soil_moisture_pct: float | None = Field(strict=True)
    soil_nitrogen_ppm: float | None = Field(strict=True)
    soil_carbon_pct: float | None = Field(strict=True)
    soil_temperature_c: float | None = Field(strict=True)
    gdd_accumulated: float | None = Field(strict=True)
    crop_biomass_kg_ha: float | None = Field(strict=True)
    leaf_area_index: float | None = Field(strict=True)
    crop_stage: str | None = Field(max_length=100)
    root_depth_cm: float | None = Field(strict=True)
    rainfall_mm: float | None = Field(strict=True)
    irrigation_mm: float | None = Field(strict=True)
    et_actual_mm: float | None = Field(strict=True)
    drainage_mm: float | None = Field(strict=True)
    temp_avg_c: float | None = Field(strict=True)
    temp_min_c: float | None = Field(strict=True)
    temp_max_c: float | None = Field(strict=True)
    solar_radiation_mj: float | None = Field(strict=True)
    humidity_pct: float | None = Field(strict=True)
    wind_speed_kmh: float | None = Field(strict=True)
    carbon_sequestered_kg_ha: float | None = Field(strict=True)
    carbon_emitted_kg_ha: float | None = Field(strict=True)


class CropSimulationRunsResponse(_CropSimulationResponseModel):
    location_id: UUID
    total_runs: int = Field(ge=0, strict=True)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)
    runs: list[CropSimulationRunResponse] = Field(max_length=50)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.runs) > self.limit:
            raise ValueError("crop simulation page exceeds requested limit")
        if self.runs and self.offset + len(self.runs) > self.total_runs:
            raise ValueError("crop simulation page exceeds total count")
        expected_has_more = (
            self.total_runs > self.offset + len(self.runs)
            and self.offset + self.limit <= 10_000
        )
        if self.has_more != expected_has_more:
            raise ValueError("crop simulation has_more does not match total count")
        return self


class CropSimulationRunDetailResponse(_CropSimulationResponseModel):
    location_id: UUID
    run: CropSimulationRunResponse
    total_states: int = Field(ge=0, strict=True)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)
    states: list[CropSimulationStateResponse] = Field(max_length=50)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.states) > self.limit:
            raise ValueError("crop simulation state page exceeds requested limit")
        if self.states and self.offset + len(self.states) > self.total_states:
            raise ValueError("crop simulation state page exceeds total count")
        expected_has_more = (
            self.total_states > self.offset + len(self.states)
            and self.offset + self.limit <= 10_000
        )
        if self.has_more != expected_has_more:
            raise ValueError("crop simulation state has_more does not match total count")
        return self


def _invalid_projection(scope: str, exc: Exception, headers: dict):
    from fastapi.responses import JSONResponse

    from services.common.logging import get_logger

    get_logger("gateway.crop_simulations").warning(
        "Crop simulation %s response rejected (%s)", scope, type(exc).__name__
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Crop simulation read unavailable"},
        headers=headers,
    )


def register_crop_simulation_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.crop_simulations import (
        get_location_crop_simulation_run_detail,
        get_location_crop_simulation_runs,
    )

    @router.get(
        "/operator/api/crop-simulations/{location_id}/runs/{run_id}",
        response_model=CropSimulationRunDetailResponse,
    )
    async def crop_simulation_run_detail(
        request: Request,
        location_id: str,
        run_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10_000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_crop_simulation_run_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                run_id,
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
            from services.common.logging import get_logger

            get_logger("gateway.crop_simulations").warning(
                "Crop simulation detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Crop simulation detail unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Completed crop simulation run not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        try:
            validated = CropSimulationRunDetailResponse.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.run.run_id != UUID(run_id)
                or validated.limit != limit
                or validated.offset != offset
            ):
                raise ValueError("crop simulation detail does not match request")
        except (ValidationError, ValueError) as exc:
            return _invalid_projection("detail", exc, headers)
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/crop-simulations/{location_id}/runs",
        response_model=CropSimulationRunsResponse,
    )
    async def crop_simulation_runs(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10_000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_crop_simulation_runs,
                request.state.operator_session.operator.operator_id,
                location_id,
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
            from services.common.logging import get_logger

            get_logger("gateway.crop_simulations").warning(
                "Crop simulation summaries unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Crop simulation summaries unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        try:
            validated = CropSimulationRunsResponse.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.limit != limit
                or validated.offset != offset
            ):
                raise ValueError("crop simulation page does not match request")
        except (ValidationError, ValueError) as exc:
            return _invalid_projection("summary", exc, headers)
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
