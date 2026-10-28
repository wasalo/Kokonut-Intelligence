"""OIDC route registration for aggregate emergency response summaries."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _EmergencyResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EmergencyIncidentTypeSummary(_EmergencyResponseModel):
    incident_type: Literal[
        "drought", "flood", "pest_outbreak", "extreme_heat", "frost", "fire",
        "disease_epidemic", "soil_degradation", "water_crisis", "other",
    ]
    count: int = Field(ge=0, strict=True)
    resolved_count: int = Field(ge=0, strict=True)
    escalated_count: int = Field(ge=0, strict=True)
    avg_affected_area_pct: float = Field(ge=0, le=100)
    financial_impact_usd: float


class EmergencySeveritySummary(_EmergencyResponseModel):
    severity: Literal["low", "medium", "high", "critical"]
    count: int = Field(ge=0, strict=True)
    resolved_count: int = Field(ge=0, strict=True)
    escalated_count: int = Field(ge=0, strict=True)
    avg_affected_area_pct: float = Field(ge=0, le=100)
    financial_impact_usd: float


class EmergencyResponseSummary(_EmergencyResponseModel):
    location_id: UUID
    total_incidents: int = Field(ge=0, strict=True)
    resolved_incidents: int = Field(ge=0, strict=True)
    escalated_incidents: int = Field(ge=0, strict=True)
    recovered_incidents: int = Field(ge=0, strict=True)
    avg_response_time_days: float | None
    deadline_assessed_incidents: int = Field(ge=0, strict=True)
    deadline_met_incidents: int = Field(ge=0, strict=True)
    deadline_compliance_pct: float | None = Field(default=None, ge=0, le=100)
    financial_impact_usd: float
    avg_affected_area_pct: float = Field(ge=0, le=100)
    by_type: list[EmergencyIncidentTypeSummary] = Field(max_length=10)
    by_severity: list[EmergencySeveritySummary] = Field(max_length=4)


def register_emergency_response_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.emergency_response import get_emergency_response_summary

    @router.get(
        "/operator/api/emergency-response/{location_id}/summary",
        response_model=EmergencyResponseSummary,
    )
    async def emergency_response_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            summary = await run_in_threadpool(
                get_emergency_response_summary,
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

            get_logger("gateway.emergency_response").warning(
                "Emergency response summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Emergency response summary unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )

        try:
            validated = EmergencyResponseSummary.model_validate(summary)
        except ValidationError as exc:
            from services.common.logging import get_logger

            get_logger("gateway.emergency_response").warning(
                "Emergency response summary rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Emergency response summary unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
