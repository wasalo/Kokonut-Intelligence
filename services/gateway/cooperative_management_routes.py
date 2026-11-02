"""OIDC routes for location-scoped cooperative operations summaries."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _CooperativeResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CooperativeGroupSummary(_CooperativeResponseModel):
    cooperative_type: Literal[
        "marketing", "input_purchase", "equipment_sharing", "processing", "other"
    ]
    cooperative_status: Literal["draft", "active", "suspended", "dissolved", "archived"]
    cooperative_count: int = Field(ge=0)
    active_member_count: int = Field(ge=0)


class CooperativeAssetSummary(_CooperativeResponseModel):
    asset_type: Literal[
        "tractor", "harvester", "irrigation_system", "storage_facility",
        "processing_equipment", "transport_vehicle", "drying_rack", "mill",
        "press", "packaging_machine", "generator", "solar_panel", "water_tank",
        "greenhouse", "other",
    ]
    asset_status: Literal[
        "available", "in_use", "under_maintenance", "reserved",
        "decommissioned", "out_of_service",
    ]
    asset_count: int = Field(ge=0)


class CooperativeBookingSummary(_CooperativeResponseModel):
    booking_status: Literal[
        "pending", "confirmed", "in_progress", "completed", "cancelled", "no_show"
    ]
    booking_count: int = Field(ge=0)


class CooperativeManagementSummaryResponse(_CooperativeResponseModel):
    location_id: UUID
    cooperatives: list[CooperativeGroupSummary]
    assets: list[CooperativeAssetSummary]
    bookings: list[CooperativeBookingSummary]


def register_cooperative_management_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.cooperative_management_reads import (
        get_location_cooperative_management_summary,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/cooperatives/{location_id}/summary",
        response_model=CooperativeManagementSummaryResponse,
    )
    async def cooperative_management_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_cooperative_management_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified cooperative access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.cooperative_management").warning(
                "Cooperative summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Cooperative summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = CooperativeManagementSummaryResponse.model_validate(result)
        except ValidationError as exc:
            from services.common.logging import get_logger

            get_logger("gateway.cooperative_management").warning(
                "Cooperative summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Cooperative summary unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers=headers,
        )
