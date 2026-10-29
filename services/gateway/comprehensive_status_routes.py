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


class ComprehensiveStatusFinancialSustainabilityPlan(_ComprehensiveStatusModel):
    """Exact row projection returned by the published-plan summary view."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    id: ReportUuid
    location_id: ReportUuid
    farm_id: ReportUuid | None
    plan_name: str = Field(min_length=1, max_length=255)
    farm_model: Literal[
        "public_good_optimized",
        "blended",
        "for_profit",
        "cooperative",
        "research_pilot",
        "other",
    ]
    plan_period_start: ReportDate
    plan_period_end: ReportDate | None
    revenue_streams: list[str] | None
    grant_dependency_pct: ReportNumber | None = Field(ge=0, le=100)
    reinvestment_pct: ReportNumber | None = Field(ge=0, le=100)
    public_goods_allocation_pct: ReportNumber | None = Field(ge=0, le=100)
    break_even_month: int | None
    runway_months: ReportNumber | None
    projected_annual_revenue_usd: ReportNumber | None
    projected_annual_operating_cost_usd: ReportNumber | None
    projected_annual_noi_usd: ReportNumber | None
    sustainability_status: Literal[
        "draft",
        "grant_dependent",
        "transitioning",
        "self_sustaining",
        "surplus_generating",
        "needs_rework",
    ] | None
    public_summary: str | None
    evidence_maturity: int = Field(ge=3, le=6, strict=True)
    evidence_maturity_label: str | None
    metadata: JsonValue


class ComprehensiveStatusFinancialSustainability(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    report_type: Literal["financial_sustainability"]
    location_id: ReportUuid
    location_name: str | None
    plans: list[ComprehensiveStatusFinancialSustainabilityPlan]
    limitations: list[str]
    generated_at: ReportDateTime

    @model_validator(mode="after")
    def keep_plans_in_scope(self):
        if any(plan.location_id != self.location_id for plan in self.plans):
            raise ValueError("Financial sustainability plan is outside report location scope")
        return self


class ComprehensiveStatusRegenerativeOutcome(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    id: ReportUuid
    location_id: ReportUuid
    farm_id: ReportUuid | None
    period_start: ReportDate
    period_end: ReportDate
    summary_name: str
    hectares_restored: ReportNumber | None = Field(ge=0)
    baseline_species_count: int | None = Field(ge=0, strict=True)
    latest_species_count: int | None = Field(ge=0, strict=True)
    species_diversity_delta: ReportNumber | None
    baseline_soil_carbon_t_ha: ReportNumber | None
    latest_soil_carbon_t_ha: ReportNumber | None
    soil_carbon_delta_t_ha: ReportNumber | None
    trees_planted_count: int | None = Field(ge=0, strict=True)
    trees_surviving_count: int | None = Field(ge=0, strict=True)
    tree_survival_rate_pct: ReportNumber | None = Field(ge=0, le=100)
    regenerative_score: ReportNumber | None = Field(ge=0, le=100)
    jobs_or_roles_supported_count: int | None = Field(ge=0, strict=True)
    training_hours: ReportNumber | None = Field(ge=0)
    beneficiary_count: int | None = Field(ge=0, strict=True)
    evidence_confidence: Literal["high", "moderate", "low", "insufficient_evidence"] | None
    public_summary: str | None
    evidence_maturity: int = Field(ge=3, le=6, strict=True)
    evidence_maturity_label: str | None
    metadata: JsonValue

    @model_validator(mode="after")
    def keep_period_order(self):
        if self.period_start > self.period_end:
            raise ValueError("Regenerative outcome period starts after it ends")
        return self


class ComprehensiveStatusRegenerativeOutcomes(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    report_type: Literal["regenerative_outcomes"]
    location_id: ReportUuid
    location_name: str | None
    outcomes: list[ComprehensiveStatusRegenerativeOutcome]
    total_hectares_restored: ReportNumber = Field(ge=0)
    limitations: list[str]
    generated_at: ReportDateTime

    @model_validator(mode="after")
    def keep_outcomes_in_scope_and_total_consistent(self):
        if any(outcome.location_id != self.location_id for outcome in self.outcomes):
            raise ValueError("Regenerative outcome is outside report location scope")
        expected_hectares = round(
            sum(float(outcome.hectares_restored or 0) for outcome in self.outcomes), 4
        )
        if self.total_hectares_restored != expected_hectares:
            raise ValueError("Regenerative outcome total does not match its rows")
        return self


class ComprehensiveStatusClimateCarbonBalance(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    location_id: ReportUuid
    reporting_year: int
    above_ground_carbon_tonnes: ReportNumber
    below_ground_carbon_tonnes: ReportNumber
    total_sequestration_tonnes_co2e: ReportNumber
    total_emissions_tonnes_co2e: ReportNumber
    net_climate_impact_tonnes_co2e: ReportNumber
    carbon_position: Literal["net_sequester", "net_emitter", "neutral"]


class ComprehensiveStatusClimateGhgCategory(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    category: str
    record_count: int = Field(ge=0)
    total_co2e_kg: ReportNumber
    total_co2e_tonnes: ReportNumber


class ComprehensiveStatusClimateGhgTotals(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    total_co2e_kg: ReportNumber
    total_co2e_tonnes: ReportNumber
    record_count: int = Field(ge=0)


class ComprehensiveStatusClimateGhgEmissions(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    location_id: ReportUuid
    period_start: ReportDate | None
    period_end: ReportDate | None
    categories: list[ComprehensiveStatusClimateGhgCategory]
    summary: ComprehensiveStatusClimateGhgTotals


class ComprehensiveStatusClimateTreeSpecies(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    species_name: str
    total_trees: int
    total_biomass_kg: ReportNumber
    total_carbon_tonnes: ReportNumber
    total_co2e_tonnes: ReportNumber
    survey_count: int = Field(ge=0)


class ComprehensiveStatusClimateTreeTotals(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    total_trees: int
    total_carbon_tonnes: ReportNumber
    total_co2e_tonnes: ReportNumber
    species_count: int = Field(ge=0)


class ComprehensiveStatusClimateTreeCarbon(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    location_id: ReportUuid
    species: list[ComprehensiveStatusClimateTreeSpecies]
    summary: ComprehensiveStatusClimateTreeTotals


class ComprehensiveStatusClimatePrinciple(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    principle_key: str
    principle_name: str
    score: int = Field(ge=0, le=5)
    max_score: Literal[5]
    assessment_date: ReportDate
    evidence_path: str | None
    notes: str | None


class ComprehensiveStatusClimateRegenerativeTotals(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    # The legacy query includes all verified/published assessment dates, so
    # accumulated totals may exceed a single five-principle 25-point scale.
    total_score: int = Field(ge=0)
    max_score: Literal[25]
    score_pct: ReportNumber = Field(ge=0)
    principles_assessed: int = Field(ge=0)
    last_assessment_date: ReportDate | None


class ComprehensiveStatusClimateRegenerativeScore(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    location_id: ReportUuid
    principles: list[ComprehensiveStatusClimatePrinciple]
    summary: ComprehensiveStatusClimateRegenerativeTotals


class ComprehensiveStatusClimateFrameworkPhase(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    framework_key: str
    phase: str
    phase_status: str
    phase_start_date: ReportDate | None
    review_cadence: str | None


class ComprehensiveStatusClimateOperationsProtocol(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    title: str
    section: str | None
    version: str


class ComprehensiveStatusClimateStoredSummary(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    id: ReportUuid
    location_id: ReportUuid
    reporting_year: int
    above_ground_carbon_tonnes: ReportNumber | None
    below_ground_carbon_tonnes: ReportNumber | None
    total_sequestration_tonnes_co2e: ReportNumber | None
    transport_emissions_tonnes_co2e: ReportNumber | None
    machinery_emissions_tonnes_co2e: ReportNumber | None
    input_emissions_tonnes_co2e: ReportNumber | None
    total_emissions_tonnes_co2e: ReportNumber | None
    net_climate_impact_tonnes_co2e: ReportNumber | None
    species_count: int | None
    shannon_index: ReportNumber | None
    regenerative_score_total: int | None
    methodology_version: str | None
    data_quality_score: ReportNumber | None
    status: str | None
    reviewed_by: ReportUuid | None
    reviewed_at: ReportDateTime | None
    notes: str | None
    source_system: str | None
    source_id: str | None
    created_at: ReportDateTime | None
    updated_at: ReportDateTime | None


class ComprehensiveStatusClimateImpact(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    report_type: Literal["climate_impact"]
    location_id: ReportUuid
    location_name: str
    reporting_year: int
    carbon_balance: ComprehensiveStatusClimateCarbonBalance
    ghg_emissions: ComprehensiveStatusClimateGhgEmissions
    tree_carbon: ComprehensiveStatusClimateTreeCarbon
    regenerative_score: ComprehensiveStatusClimateRegenerativeScore
    framework_phases: list[ComprehensiveStatusClimateFrameworkPhase]
    # Active operations protocols are intentionally shared platform metadata,
    # as stated by the generator's limitations field.
    operations_protocols: list[ComprehensiveStatusClimateOperationsProtocol]
    stored_summary: ComprehensiveStatusClimateStoredSummary | None
    limitations: list[str]
    generated_at: ReportDateTime

    @model_validator(mode="after")
    def keep_calculations_and_stored_summary_in_scope(self):
        nested_location_ids = (
            self.carbon_balance.location_id,
            self.ghg_emissions.location_id,
            self.tree_carbon.location_id,
            self.regenerative_score.location_id,
        )
        if any(location_id != self.location_id for location_id in nested_location_ids):
            raise ValueError("Climate impact calculation is outside report location scope")
        if self.carbon_balance.reporting_year != self.reporting_year:
            raise ValueError("Climate impact carbon balance is outside report year scope")
        if self.stored_summary is not None and (
            self.stored_summary.location_id != self.location_id
            or self.stored_summary.reporting_year != self.reporting_year
        ):
            raise ValueError("Climate impact stored summary is outside report location/year scope")
        return self


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


class ComprehensiveStatusFarmLocation(_ComprehensiveStatusModel):
    """Current location projection embedded in the farm-summary report."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    id: ReportUuid
    name: str
    slug: str
    description: str | None
    country: str | None
    region: str | None
    sub_region: str | None
    timezone: str | None
    latitude: ReportNumber | None
    longitude: ReportNumber | None
    baseline_revenue: ReportNumber | None
    baseline_asset_value: ReportNumber | None
    baseline_cash_flow: ReportNumber | None
    baseline_cost: ReportNumber | None
    baseline_assumptions: JsonValue
    baseline_source: str | None
    baseline_date: ReportDate | None
    status: str | None
    metadata: JsonValue
    created_at: ReportDateTime | None
    updated_at: ReportDateTime | None
    created_by: ReportUuid | None
    updated_by: ReportUuid | None
    project_url: str | None
    project_start_date: ReportDate | None
    project_end_date: ReportDate | None
    bioregion: list[str] | None
    biome_type: list[str] | None
    watershed: str | None
    sub_watershed: str | None
    schema_version: str | None
    organization_id: ReportUuid | None
    baseline_recorded_at: ReportDateTime | None


class ComprehensiveStatusFarmRecord(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    id: ReportUuid
    location_id: ReportUuid
    name: str
    slug: str
    description: str | None
    farm_type: str | None
    total_area: ReportNumber | None
    area_unit: str | None
    # PostGIS driver serialization is deliberately left JSON-compatible until
    # the separate geometry exposure review establishes its runtime shape.
    boundary: JsonValue
    center: JsonValue
    status: str | None
    metadata: JsonValue
    created_at: ReportDateTime | None
    updated_at: ReportDateTime | None
    created_by: ReportUuid | None
    updated_by: ReportUuid | None
    property_id: ReportUuid | None
    schema_version: str | None
    logo_url: str | None
    logo_file_id: ReportUuid | None
    traditional_name: str | None
    languages: list[str] | None
    global_standard_certifications: list[str] | None
    economic_sectors: list[str] | None
    credits_registries: list[str] | None
    data_privacy_status: str | None
    data_privacy_standard: str | None
    data_privacy_criteria: JsonValue


class ComprehensiveStatusFarmPlot(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    id: ReportUuid
    farm_id: ReportUuid
    name: str
    slug: str
    description: str | None
    area: ReportNumber | None
    area_unit: str | None
    # Keep the current geometry values intact while their encoded form is
    # reviewed independently.
    boundary: JsonValue
    center: JsonValue
    soil_type: str | None
    water_source: str | None
    elevation_m: ReportNumber | None
    slope_pct: ReportNumber | None
    aspect: str | None
    status: str | None
    metadata: JsonValue
    created_at: ReportDateTime | None
    updated_at: ReportDateTime | None
    created_by: ReportUuid | None
    updated_by: ReportUuid | None
    schema_version: str | None
    bed_count: int | None
    bed_area_sqm: ReportNumber | None
    farm_name: str


class ComprehensiveStatusFarmCropCycle(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    id: ReportUuid
    plot_id: ReportUuid
    crop_id: ReportUuid
    location_id: ReportUuid
    cycle_name: str | None
    season: str | None
    planting_date: ReportDate | None
    expected_harvest_date: ReportDate | None
    actual_harvest_date: ReportDate | None
    expected_yield: ReportNumber | None
    expected_yield_unit: str | None
    actual_yield: ReportNumber | None
    actual_yield_unit: str | None
    expected_price_per_unit: ReportNumber | None
    expected_revenue: ReportNumber | None
    actual_revenue: ReportNumber | None
    planting_density: ReportNumber | None
    planting_density_unit: str | None
    area_planted: ReportNumber | None
    area_unit: str | None
    status: str | None
    failure_reason: str | None
    metadata: JsonValue
    schema_version: str | None
    created_at: ReportDateTime | None
    updated_at: ReportDateTime | None
    created_by: ReportUuid | None
    updated_by: ReportUuid | None
    crop_name: str
    plot_name: str


class ComprehensiveStatusFarmHarvestSummary(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    total_harvests: int = Field(ge=0)
    total_quantity: ReportNumber | None
    avg_harvest_size: ReportNumber | None
    cycles_with_harvest: int = Field(ge=0)
    quantity_unit: str | None
    total_quantity_by_unit: dict[str, ReportNumber]


class ComprehensiveStatusFarmFinancialSummary(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    total_revenue: ReportNumber
    total_expenses: ReportNumber
    net_income: ReportNumber


class ComprehensiveStatusFarmExpenseCategory(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    category: str
    total: ReportNumber


class ComprehensiveStatusFarmAttestationCoverage(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    total_records: int = Field(ge=0)
    attested: int = Field(ge=0)
    draft: int = Field(ge=0)


class ComprehensiveStatusFarmActivityType(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    activity_type: str
    activity_count: int = Field(ge=0)
    reported_labor_hours: ReportNumber
    reported_labor_hours_unit: Literal["hours"]


class ComprehensiveStatusFarmActivitySummary(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    published_activity_count: int = Field(ge=0)
    reported_labor_hours: ReportNumber
    reported_labor_hours_unit: Literal["hours"]
    by_activity_type: list[ComprehensiveStatusFarmActivityType]


class ComprehensiveStatusFarmSummary(_ComprehensiveStatusModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)

    report_type: Literal["farm_summary"]
    location: ComprehensiveStatusFarmLocation
    farms: list[ComprehensiveStatusFarmRecord]
    plots: list[ComprehensiveStatusFarmPlot]
    crop_cycles: list[ComprehensiveStatusFarmCropCycle]
    harvest_summary: ComprehensiveStatusFarmHarvestSummary
    financial_summary: ComprehensiveStatusFarmFinancialSummary
    expense_breakdown: list[ComprehensiveStatusFarmExpenseCategory]
    attestation_coverage: ComprehensiveStatusFarmAttestationCoverage
    farm_activity_summary: ComprehensiveStatusFarmActivitySummary
    generated_at: ReportDateTime


class ComprehensiveStatusSections(_ComprehensiveStatusModel):
    farm_summary: ComprehensiveStatusFarmSummary | ComprehensiveStatusSectionError
    crop_noi: ComprehensiveStatusCropNoiReport | ComprehensiveStatusSectionError
    environmental: ComprehensiveStatusEnvironmental | ComprehensiveStatusSectionError
    climate_impact: ComprehensiveStatusClimateImpact | ComprehensiveStatusSectionError
    financial_sustainability: (
        ComprehensiveStatusFinancialSustainability | ComprehensiveStatusSectionError
    )
    regenerative_outcomes: (
        ComprehensiveStatusRegenerativeOutcomes | ComprehensiveStatusSectionError
    )
    capital_efficiency: JsonValue
    holistic_wellbeing: JsonValue
    community_governance: JsonValue
    gnh_alignment: JsonValue
    training_impact: JsonValue
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
        financial = self.sections.financial_sustainability
        if (
            isinstance(financial, ComprehensiveStatusFinancialSustainability)
            and financial.location_id != self.location_id
        ):
            raise ValueError("Financial sustainability section is outside the composed location scope")
        climate = self.sections.climate_impact
        if (
            isinstance(climate, ComprehensiveStatusClimateImpact)
            and climate.location_id != self.location_id
        ):
            raise ValueError("Climate impact section is outside the composed location scope")
        regenerative = self.sections.regenerative_outcomes
        if (
            isinstance(regenerative, ComprehensiveStatusRegenerativeOutcomes)
            and regenerative.location_id != self.location_id
        ):
            raise ValueError("Regenerative outcomes section is outside the composed location scope")
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
