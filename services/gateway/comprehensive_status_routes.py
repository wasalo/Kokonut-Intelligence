"""OIDC routes for location-scoped Comprehensive Status reports."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    field_validator,
    model_validator,
)


class _ComprehensiveStatusModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


_COMPREHENSIVE_STATUS_SECTIONS = frozenset(
    {
        "farm_summary",
        "crop_noi",
        "environmental",
        "climate_impact",
        "financial_sustainability",
        "capital_efficiency",
        "holistic_wellbeing",
        "community_governance",
        "gnh_alignment",
        "training_impact",
        "regenerative_outcomes",
        "foundational_wellbeing",
        "stakeholder_outcomes",
        "capital_accounting",
    }
)


class ComprehensiveStatusLocation(_ComprehensiveStatusModel):
    location_id: UUID
    name: str | None
    slug: str | None
    country: str | None
    region: str | None
    sections: dict[str, JsonValue] = Field(min_length=14, max_length=14)

    @field_validator("sections")
    @classmethod
    def require_canonical_sections(cls, value):
        if value.keys() != _COMPREHENSIVE_STATUS_SECTIONS:
            raise ValueError("Comprehensive Status sections are incomplete or unknown")
        return value


class ComprehensiveStatusOverview(_ComprehensiveStatusModel):
    total_locations: int = Field(ge=0, strict=True)
    locations_with_financial_data: int = Field(ge=0, strict=True)
    total_revenue_usd: float
    total_expenses_usd: float
    net_income_usd: float
    total_harvest_quantity: float | None
    total_harvest_quantity_unit: str | None
    total_harvest_quantity_by_unit: dict[str, float]


class ComprehensiveStatusResponse(_ComprehensiveStatusModel):
    report_type: Literal["comprehensive_status"]
    scope: Literal["selected_locations"]
    selected_location_ids: list[UUID] = Field(min_length=1, max_length=1)
    period_start: date | None
    period_end: date | None
    ecosystem_overview: ComprehensiveStatusOverview
    locations: list[ComprehensiveStatusLocation] = Field(max_length=1)
    limitations: list[str] = Field(max_length=16)
    generated_at: datetime

    @model_validator(mode="after")
    def keep_composed_location_inside_selected_scope(self):
        selected_location_id = self.selected_location_ids[0]
        if any(location.location_id != selected_location_id for location in self.locations):
            raise ValueError("Comprehensive Status location is outside the selected scope")
        return self


def register_comprehensive_status_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.comprehensive_status_reads import (
        MAX_COMPREHENSIVE_STATUS_BYTES,
        ComprehensiveStatusPayloadTooLarge,
        ComprehensiveStatusReadInvalid,
        get_location_comprehensive_status,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/comprehensive-status/{location_id}",
        response_model=ComprehensiveStatusResponse,
    )
    async def location_comprehensive_status(
        request: Request,
        location_id: str,
        period_start: str | None = None,
        period_end: str | None = None,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_comprehensive_status,
                request.state.operator_session.operator.operator_id,
                location_id,
                period_start=period_start,
                period_end=period_end,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "A tenant-qualified Comprehensive Status read grant is required"},
                headers=headers,
            )
        except ComprehensiveStatusReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except ComprehensiveStatusPayloadTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location Comprehensive Status read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.comprehensive_status").warning(
                "Comprehensive Status read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Comprehensive Status read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = ComprehensiveStatusResponse.model_validate(
                jsonable_encoder(result)
            )
            if validated.selected_location_ids != [UUID(location_id)]:
                raise ValueError("Comprehensive Status scope does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.comprehensive_status").warning(
                "Comprehensive Status response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Comprehensive Status read unavailable"},
                headers=headers,
            )
        response = JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
        if len(response.body) > MAX_COMPREHENSIVE_STATUS_BYTES:
            return JSONResponse(
                status_code=413,
                content={"error": "Comprehensive Status exceeds the 512 KiB response limit"},
                headers=headers,
            )
        return response
