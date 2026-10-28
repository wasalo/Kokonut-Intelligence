"""OIDC routes for location-scoped Comprehensive Status reports."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    model_validator,
)


def _report_uuid(value):
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise ValueError("Report identifiers must be UUID strings")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("Report identifier is invalid") from exc


def _report_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError("Report dates must be ISO strings")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Report date is invalid") from exc
    if parsed.isoformat() != value:
        raise ValueError("Report date is not canonical")
    return parsed


def _report_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Report timestamp is invalid") from exc
        if parsed.isoformat() != value:
            raise ValueError("Report timestamp is not canonical")
    else:
        raise ValueError("Report timestamps must be ISO strings")
    if parsed.utcoffset() is None:
        raise ValueError("Report timestamp must include a timezone")
    return parsed


def _report_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Report measures must be numeric values")
    return float(value)


ReportUuid = Annotated[UUID, BeforeValidator(_report_uuid)]
ReportDate = Annotated[date, BeforeValidator(_report_date)]
ReportDateTime = Annotated[datetime, BeforeValidator(_report_datetime)]
ReportNumber = Annotated[float, BeforeValidator(_report_number)]


class _ComprehensiveStatusModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ComprehensiveStatusCropNoiCycle(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    cycle_id: ReportUuid
    cycle_name: str | None
    crop_name: str
    plot_name: str
    status: str | None
    planting_date: ReportDate | None
    actual_harvest_date: ReportDate | None
    expected_yield: ReportNumber
    actual_yield: ReportNumber
    expected_revenue: ReportNumber
    actual_revenue: ReportNumber
    allocated_cost: ReportNumber
    gross_revenue: ReportNumber
    returns_and_discounts: ReportNumber
    net_revenue: ReportNumber
    direct_crop_costs: ReportNumber
    allocated_shared_costs: ReportNumber
    total_costs: ReportNumber
    crop_noi: ReportNumber
    operating_margin_pct: ReportNumber
    loss_rate_pct: ReportNumber


class ComprehensiveStatusCropNoiSummary(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    total_revenue: ReportNumber
    total_gross_revenue: ReportNumber
    total_returns_and_discounts: ReportNumber
    total_direct_crop_costs: ReportNumber
    total_allocated_shared_costs: ReportNumber
    total_cost: ReportNumber
    total_noi: ReportNumber
    overall_margin_pct: ReportNumber


class ComprehensiveStatusCropNoiReport(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    report_type: Literal["crop_noi"]
    location_id: ReportUuid
    crop_cycles: list[ComprehensiveStatusCropNoiCycle]
    summary: ComprehensiveStatusCropNoiSummary
    generated_at: ReportDateTime


class ComprehensiveStatusSectionError(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    error: str = Field(
        max_length=100,
        pattern=r"^report section failed \([A-Za-z_][A-Za-z0-9_]{0,63}\)$",
    )


class ComprehensiveStatusEnvironmentalSoilCarbon(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    measurement_date: ReportDate
    carbon_tonnes_per_ha: ReportNumber | None
    measurement_method: str | None
    depth_cm: ReportNumber | None


class ComprehensiveStatusEnvironmentalSpecies(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    observation_date: ReportDate
    count: int | None
    habitat_type: str | None
    notes: str | None


class ComprehensiveStatusEnvironmentalRemoteSensing(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    observation_date: ReportDate
    ndvi: ReportNumber | None
    ndre: ReportNumber | None
    cloud_cover_pct: ReportNumber | None


class ComprehensiveStatusEnvironmentalLoss(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    loss_date: ReportDate
    loss_type: str
    quantity: ReportNumber | None
    unit: str | None
    cause: str | None


class ComprehensiveStatusEnvironmental(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    report_type: Literal["environmental"]
    location_id: ReportUuid
    soil_carbon: list[ComprehensiveStatusEnvironmentalSoilCarbon]
    species_observations: list[ComprehensiveStatusEnvironmentalSpecies]
    remote_sensing: list[ComprehensiveStatusEnvironmentalRemoteSensing]
    loss_events: list[ComprehensiveStatusEnvironmentalLoss]
    generated_at: ReportDateTime


class ComprehensiveStatusSections(_ComprehensiveStatusModel):
    farm_summary: JsonValue
    crop_noi: ComprehensiveStatusCropNoiReport | ComprehensiveStatusSectionError
    environmental: ComprehensiveStatusEnvironmental | ComprehensiveStatusSectionError
    climate_impact: JsonValue
    financial_sustainability: JsonValue
    capital_efficiency: JsonValue
    holistic_wellbeing: JsonValue
    community_governance: JsonValue
    gnh_alignment: JsonValue
    training_impact: JsonValue
    regenerative_outcomes: JsonValue
    foundational_wellbeing: JsonValue
    stakeholder_outcomes: JsonValue
    capital_accounting: JsonValue


class ComprehensiveStatusLocation(_ComprehensiveStatusModel):
    location_id: UUID
    name: str | None
    slug: str | None
    country: str | None
    region: str | None
    sections: ComprehensiveStatusSections

    @model_validator(mode="after")
    def keep_location_sections_in_scope(self):
        section = self.sections.crop_noi
        if (
            isinstance(section, ComprehensiveStatusCropNoiReport)
            and section.location_id != self.location_id
        ):
            raise ValueError("Crop NOI section is outside the composed location scope")
        environmental = self.sections.environmental
        if (
            isinstance(environmental, ComprehensiveStatusEnvironmental)
            and environmental.location_id != self.location_id
        ):
            raise ValueError("Environmental section is outside the composed location scope")
        return self


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
