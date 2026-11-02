"""OIDC route registration for location-scoped irrigation status reads."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _IrrigationResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class IrrigationZoneStatus(_IrrigationResponseModel):
    zone_id: UUID
    name: str
    zone_code: str | None
    soil_type: str | None
    area_m2: float | None
    depth_cm: float | None
    zone_status: Literal["active"]
    current_moisture_pct: float | None
    last_moisture_reading: datetime | None
    moisture_status: Literal[
        "no_data", "below_trigger", "below_target", "in_range", "above_target"
    ]
    target_min_pct: float | None
    target_max_pct: float | None
    irrigation_trigger_pct: float | None
    refill_to_pct: float | None
    growth_stage: str | None
    next_irrigation_start: datetime | None
    next_irrigation_volume_l: float | None
    next_irrigation_status: Literal["pending"] | None
    last_irrigation_at: datetime | None
    last_irrigation_volume_l: float | None


class IrrigationStatusResponse(_IrrigationResponseModel):
    location_id: UUID
    total_active_zones: int = Field(ge=0, strict=True)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool
    zones: list[IrrigationZoneStatus] = Field(max_length=50)


def register_irrigation_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.irrigation_status import get_location_irrigation_status

    @router.get(
        "/operator/api/irrigation/{location_id}/status",
        response_model=IrrigationStatusResponse,
    )
    async def irrigation_status(
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
                get_location_irrigation_status,
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

            get_logger("gateway.irrigation").warning(
                "Irrigation status unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Irrigation status unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )
        try:
            validated = IrrigationStatusResponse.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.limit != limit
                or validated.offset != offset
                or len(validated.zones) > limit
                or validated.has_more
                != (validated.total_active_zones > offset + len(validated.zones))
            ):
                raise ValueError("Irrigation status scope does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.irrigation").warning(
                "Irrigation status response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Irrigation status unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
