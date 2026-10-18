from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

JSONScalar = Union[str, int, float, bool, None]
JSONValue = Union[JSONScalar, List["JSONValue"], Dict[str, "JSONValue"]]
JSONObject = Dict[str, JSONValue]
LifecycleStatus = Literal["draft", "submitted", "verified", "published", "rejected"]
EntityStatus = Literal["active", "inactive", "archived"]
EntityStatusExtended = Literal["active", "inactive", "maintenance", "decommissioned"]
PaymentStatus = Literal["pending", "partial", "paid", "overdue", "cancelled"]
SensorSeverity = Literal["info", "warning", "critical"]
AlertLifecycle = Literal["open", "acknowledged", "resolved", "false_positive"]
ExportStatus = Literal["pending", "generating", "completed", "failed"]
OrganizationType = Literal["cooperative", "nonprofit", "dao", "enterprise", "collective", "other"]
OrganizationStatus = Literal["active", "inactive", "dissolved"]
OrganizationMembershipType = Literal["owned", "affiliated", "sponsored", "partner"]
OrganizationMemberRole = Literal["primary", "satellite", "partner", "incubated"]
OrganizationMemberStatus = Literal["active", "inactive", "suspended"]
ActuatorType = Literal["irrigation", "pest_control", "fertilization", "notification", "custom"]
ActuationLogStatus = Literal[
    "pending", "requires_approval", "approved", "sent", "acknowledged",
    "executed", "failed", "cancelled"
]
ActuationStatus = Literal[
    "pending", "sent", "acknowledged", "executed", "failed", "requires_approval"
]
SensorAnomalyEffectOutcome = Literal["no_match", "cooldown", "alert_created"]
AttestationVerdict = Literal["pending", "approved", "rejected", "needs_info"]
TimeSeriesForecastModelType = Literal[
    "arima", "exponential_smoothing", "prophet", "naive", "seasonal_naive"
]
TimeSeriesForecastStatus = Literal["active", "superseded", "expired"]
DemandForecastType = Literal[
    "time_series", "buyer_pipeline", "seasonal_decomposition", "hybrid"
]
DemandForecastStatus = Literal["draft", "submitted", "verified", "published"]
MarketScope = Literal["local", "regional", "national", "international"]
PriceAggregationMethod = Literal[
    "single", "median_consensus", "weighted_average", "on_chain_attested"
]
MarketSizeEstimateStatus = Literal["draft", "submitted", "verified", "published"]
DemandTrendAnalysisType = Literal[
    "seasonal_pattern", "price_elasticity", "moving_average", "trend_decomposition"
]
DemandTrendStatus = Literal["draft", "submitted", "verified", "published"]
BuyerSignalType = Literal[
    "verbal_intent", "written_order", "purchase_order", "forecast_request", "recurring_order"
]
BuyerType = Literal[
    "processor", "direct", "market", "restaurant", "retailer", "export", "cooperative", "other"
]
BuyerCommitmentLevel = Literal["firm", "probable", "possible", "exploratory"]
BuyerSignalStatus = Literal["draft", "submitted", "verified", "published", "rejected"]
BuyerSegmentType = Literal["value_based", "behavior_based", "need_based", "tier_based"]
BuyerSegmentValue = Literal[
    "high_value", "medium_value", "low_value", "potential", "at_risk", "churned"
]
TrendDirection = Literal["improving", "stable", "declining", "insufficient_data"]
TrendConfidenceLevel = Literal["high", "moderate", "low", "insufficient_data"]
TrendSmoothingType = Literal[
    "moving_average", "weighted_moving_average", "exponential", "holt_linear"
]
ChangePointDetectionMethod = Literal["cusum", "pelt", "binary_segmentation", "window_slider"]
ChangePointDirection = Literal["increase", "decrease", "variance_change"]
ChangePointStatus = Literal["detected", "confirmed", "dismissed"]
SeasonalDecompositionMethod = Literal["classical", "stl", "x11"]
TrophicLevel = Literal[
    "producer", "primary_consumer", "secondary_consumer", "decomposer", "omnivore"
]
ConservationStatus = Literal[
    "critically_endangered",
    "endangered",
    "vulnerable",
    "near_threatened",
    "least_concern",
    "data_deficient",
    "not_evaluated",
]
FarmTaskCategory = Literal[
    "planting", "weeding", "irrigation", "spraying", "harvesting", "maintenance",
    "training", "reporting", "other",
]
FarmTaskPriority = Literal["low", "medium", "high", "critical"]
FarmTaskStatus = Literal["pending", "in_progress", "completed", "cancelled"]
CarbonCreditStatus = Literal["draft", "submitted", "verified", "published", "retired", "revoked", "rejected"]
CreditAdjustmentStatus = Literal["draft", "submitted", "verified", "published", "rejected"]
CreditAdjustmentType = Literal["measurement_update", "methodology_change", "reversal", "correction"]
CreditAdjustmentTriggerSource = Literal[
    "tree_inventory", "soil_carbon_measurement", "ghg_emissions_inventory",
    "climate_impact_summary", "remote_sensing", "manual_override"
]
CreditRetirementStatus = Literal["draft", "submitted", "verified", "published", "rejected", "cancelled"]
CreditTransferStatus = Literal["draft", "submitted", "verified", "published", "rejected"]
CreditTransferType = Literal["allocation", "sale", "grant", "internal_rebalance"]

GeoJSONPosition = List[float]


class GeoJSONPoint(TypedDict):
    """GeoJSON point returned for PostGIS POINT columns."""

    type: Literal["Point"]
    coordinates: GeoJSONPosition


class GeoJSONPolygon(TypedDict):
    """GeoJSON polygon returned for PostGIS POLYGON columns."""

    type: Literal["Polygon"]
    coordinates: List[List[GeoJSONPosition]]


class ActivityTypeSourceOption(TypedDict):
    """Preserved source option metadata; it does not select the canonical activity type."""

    option_id: int
    label: str


@dataclass
class ListOptions:
    filter: Optional[Dict[str, Any]] = None
    sort: Optional[List[str]] = None
    fields: Optional[List[str]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    page: Optional[int] = None
    meta: Optional[str] = None

    def to_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if self.filter is not None:
            params["filter"] = self.filter
        if self.sort is not None:
            params["sort"] = self.sort
        if self.fields is not None:
            params["fields"] = self.fields
        if self.limit is not None:
            params["limit"] = self.limit
        if self.offset is not None and self.limit is not None:
            if self.limit == 0:
                raise ValueError("offset pagination requires a non-zero limit")
            params["offset"] = self.offset
        elif self.page is not None:
            params["page"] = self.page
        if self.meta is not None:
            params["meta"] = self.meta
        return params


@dataclass
class Location:
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    project_url: Optional[str] = None
    project_start_date: Optional[str] = None
    project_end_date: Optional[str] = None
    boundary: Optional[GeoJSONPolygon] = None
    center: Optional[GeoJSONPoint] = None
    country: Optional[str] = None
    region: Optional[str] = None
    sub_region: Optional[str] = None
    timezone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    baseline_revenue: Optional[float] = None
    baseline_asset_value: Optional[float] = None
    baseline_cash_flow: Optional[float] = None
    baseline_cost: Optional[float] = None
    baseline_assumptions: Optional[JSONObject] = None
    baseline_source: Optional[str] = None
    baseline_date: Optional[str] = None
    baseline_recorded_at: Optional[str] = None
    bioregion: Optional[List[str]] = None
    biome_type: Optional[List[str]] = None
    watershed: Optional[str] = None
    sub_watershed: Optional[str] = None
    organization_id: Optional[str] = None
    schema_version: Optional[str] = None
    status: Optional[EntityStatus] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class Organization:
    """Organization record; membership rows do not grant tenant access."""

    id: str
    org_key: str
    name: str
    created_at: str
    updated_at: str
    org_type: OrganizationType = "cooperative"
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    legal_entity_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    governance_model: Optional[str] = None
    status: OrganizationStatus = "active"
    metadata: Optional[JSONObject] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class OrganizationMember:
    """Descriptive organization/location link; it does not grant tenant access."""

    id: str
    organization_id: str
    location_id: str
    join_date: str
    created_at: str
    updated_at: str
    team_id: Optional[str] = None
    farm_id: Optional[str] = None
    membership_type: OrganizationMembershipType = "owned"
    role: OrganizationMemberRole = "primary"
    status: OrganizationMemberStatus = "active"
    metadata: Optional[JSONObject] = None


@dataclass
class InfrastructureAsset:
    """Stored farm infrastructure inventory; this record does not assess condition."""

    id: str
    location_id: str
    name: str
    asset_type: str
    plot_id: Optional[str] = None
    description: Optional[str] = None
    install_date: Optional[str] = None
    capacity: Optional[float] = None
    capacity_unit: Optional[str] = None
    condition_status: Optional[str] = None
    last_inspection_date: Optional[str] = None
    replacement_cost: Optional[float] = None
    metadata: Optional[JSONObject] = None
    status: Optional[EntityStatusExtended] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    schema_version: Optional[str] = None


@dataclass
class Farm:
    id: str
    location_id: str
    name: str
    slug: str
    description: Optional[str] = None
    boundary: Optional[GeoJSONPolygon] = None
    center: Optional[GeoJSONPoint] = None
    logo_url: Optional[str] = None
    logo_file_id: Optional[str] = None
    property_id: Optional[str] = None
    traditional_name: Optional[str] = None
    languages: Optional[List[str]] = None
    global_standard_certifications: Optional[List[str]] = None
    economic_sectors: Optional[List[str]] = None
    credits_registries: Optional[List[str]] = None
    data_privacy_status: Optional[str] = None
    data_privacy_standard: Optional[str] = None
    data_privacy_criteria: Optional[JSONObject] = None
    farm_type: Optional[str] = None
    total_area: Optional[float] = None
    area_unit: Optional[str] = None
    status: Optional[EntityStatus] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    schema_version: Optional[str] = None


@dataclass
class Plot:
    id: str
    farm_id: str
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    boundary: Optional[GeoJSONPolygon] = None
    center: Optional[GeoJSONPoint] = None
    area: Optional[float] = None
    area_unit: Optional[str] = None
    soil_type: Optional[str] = None
    water_source: Optional[str] = None
    elevation_m: Optional[float] = None
    bed_count: Optional[int] = None
    bed_area_sqm: Optional[float] = None
    slope_pct: Optional[float] = None
    aspect: Optional[str] = None
    status: Optional[EntityStatus] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    schema_version: Optional[str] = None


@dataclass
class Crop:
    """Stored crop reference; this record does not estimate or verify yields."""

    id: str
    name: str
    scientific_name: Optional[str] = None
    variety: Optional[str] = None
    crop_category: Optional[str] = None
    growing_season_days: Optional[int] = None
    expected_yield_per_ha: Optional[float] = None
    expected_yield_unit: Optional[str] = None
    water_needs: Optional[str] = None
    climate_zone: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    schema_version: Optional[str] = None


@dataclass
class CropCycle:
    id: str
    plot_id: str
    crop_id: str
    location_id: str
    cycle_name: Optional[str] = None
    season: Optional[str] = None
    planting_date: Optional[str] = None
    expected_harvest_date: Optional[str] = None
    actual_harvest_date: Optional[str] = None
    expected_yield: Optional[float] = None
    expected_yield_unit: Optional[str] = None
    actual_yield: Optional[float] = None
    actual_yield_unit: Optional[str] = None
    expected_price_per_unit: Optional[float] = None
    expected_revenue: Optional[float] = None
    actual_revenue: Optional[float] = None
    planting_density: Optional[float] = None
    planting_density_unit: Optional[str] = None
    area_planted: Optional[float] = None
    area_unit: Optional[str] = None
    status: Optional[str] = None
    failure_reason: Optional[str] = None
    metadata: Optional[JSONObject] = None
    schema_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class FarmActivity:
    """Stored farm operation record; this model does not advance its review lifecycle."""

    id: str
    location_id: str
    activity_type: str
    activity_date: str
    plot_id: Optional[str] = None
    crop_cycle_id: Optional[str] = None
    description: Optional[str] = None
    labor_hours: Optional[float] = None
    labor_cost: Optional[float] = None
    materials_used: Optional[JSONValue] = None
    evidence_urls: Optional[List[str]] = None
    evidence_hashes: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    submitted_at: Optional[str] = None
    farm_id: Optional[str] = None
    farm_task_id: Optional[str] = None
    duration_minutes: Optional[int] = None
    activity_end_date: Optional[str] = None
    activity_type_source_options: Optional[List[ActivityTypeSourceOption]] = None


@dataclass
class FarmTask:
    """Stored farm-task plan; this record does not assign or complete work."""

    id: str
    location_id: str
    task_name: str
    category: FarmTaskCategory
    priority: FarmTaskPriority
    status: FarmTaskStatus
    farm_id: Optional[str] = None
    plot_id: Optional[str] = None
    crop_cycle_id: Optional[str] = None
    assignee_id: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None
    notes: Optional[str] = None
    metadata: Optional[JSONObject] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class FarmTaskDependency:
    """Directed task-prerequisite edge, stored without evaluating task readiness."""

    task_id: str
    prerequisite_task_id: str
    source_system: Optional[str] = None
    source_database_id: Optional[int] = None
    source_table_id: Optional[int] = None
    source_field_id: Optional[int] = None
    source_row_id: Optional[int] = None
    source_related_table_id: Optional[int] = None
    source_related_row_id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class FarmTaskFrameworkStep:
    """Task-to-framework-step association record."""

    task_id: str
    framework_step_id: str
    source_system: Optional[str] = None
    source_database_id: Optional[int] = None
    source_table_id: Optional[int] = None
    source_field_id: Optional[int] = None
    source_row_id: Optional[int] = None
    source_related_table_id: Optional[int] = None
    source_related_row_id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class FarmTaskWeeklyPlan:
    """Task-to-weekly-plan association record."""

    task_id: str
    weekly_plan_id: str
    source_system: Optional[str] = None
    source_database_id: Optional[int] = None
    source_table_id: Optional[int] = None
    source_field_id: Optional[int] = None
    source_row_id: Optional[int] = None
    source_related_table_id: Optional[int] = None
    source_related_row_id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class HarvestEvent:
    id: str
    crop_cycle_id: str
    plot_id: str
    location_id: str
    harvest_date: str
    quantity: float
    unit: str
    quality_grade: Optional[str] = None
    destination: Optional[str] = None
    loss_amount: Optional[float] = None
    loss_unit: Optional[str] = None
    loss_reason: Optional[str] = None
    loss_estimated_value: Optional[float] = None
    evidence_urls: Optional[List[str]] = None
    evidence_hashes: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    submitted_at: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class SalesEvent:
    id: str
    location_id: str
    sale_date: str
    quantity: float
    unit: str
    total_amount: float
    harvest_id: Optional[str] = None
    crop_cycle_id: Optional[str] = None
    partner_id: Optional[str] = None
    buyer: Optional[str] = None
    buyer_type: Optional[str] = None
    price_per_unit: Optional[float] = None
    currency: Optional[str] = None
    payment_status: Optional[PaymentStatus] = None
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    invoice_number: Optional[str] = None
    return_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    net_amount: Optional[float] = None
    evidence_urls: Optional[List[str]] = None
    evidence_hashes: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    submitted_at: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class ExpenseEvent:
    id: str
    location_id: str
    expense_date: str
    category: str
    amount: float
    plot_id: Optional[str] = None
    crop_cycle_id: Optional[str] = None
    farm_id: Optional[str] = None
    farm_task_id: Optional[str] = None
    weekly_plan_id: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    vendor: Optional[str] = None
    vendor_id: Optional[str] = None
    currency: Optional[str] = None
    payment_status: Optional[str] = None
    people_impacted_count: Optional[int] = None
    weekly_plan_scope_exception: Optional[bool] = None
    weekly_plan_scope_exception_reason: Optional[str] = None
    is_capex: Optional[bool] = None
    allocation_method: Optional[str] = None
    allocation_weight: Optional[float] = None
    evidence_urls: Optional[List[str]] = None
    invoice_number: Optional[str] = None
    receipt_hash: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    submitted_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class ExpenseCategory:
    """Descriptive entry in the shared expense taxonomy."""

    id: str
    name: str
    code: Optional[str] = None
    parent_id: Optional[str] = None
    description: Optional[str] = None
    is_direct: Optional[bool] = None
    allocation_default: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None
    schema_version: Optional[str] = None


@dataclass
class CapitalSource:
    """Descriptive record of a funding source and its declared terms."""

    id: str
    name: str
    source_type: str
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    terms: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[EntityStatus] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    schema_version: Optional[str] = None


@dataclass
class FinancialTransaction:
    """Recorded financial fact; this model does not initiate payments."""

    id: str
    location_id: str
    transaction_date: str
    transaction_type: str
    amount: float
    capital_source_id: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    amount_usd: Optional[float] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    counterparty: Optional[str] = None
    payment_method: Optional[str] = None
    reconciled: Optional[bool] = None
    reconciled_at: Optional[str] = None
    bank_reference: Optional[str] = None
    evidence_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class ValueFlowEvent:
    """Descriptive value-flow record; it does not perform verification or attest."""

    id: str
    flow_date: str
    flow_type: str
    amount: float
    location_id: Optional[str] = None
    from_entity: Optional[str] = None
    to_entity: Optional[str] = None
    currency: Optional[str] = None
    token: Optional[str] = None
    chain: Optional[str] = None
    tx_hash: Optional[str] = None
    description: Optional[str] = None
    verified: Optional[bool] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    attestation_uid: Optional[str] = None
    is_excluded: Optional[bool] = None
    exclusion_reason: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class ExcludedValueEvent:
    """Record of an excluded value-flow amount; it does not mutate the flow."""

    id: str
    exclusion_type: str
    reason: str
    value_flow_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    excluded_by: Optional[str] = None
    excluded_at: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class CropCostAllocation:
    """Recorded cost-to-cycle allocation; it does not calculate or transfer funds."""

    id: str
    crop_cycle_id: str
    expense_id: str
    allocation_method: str
    allocated_amount: float
    allocation_ratio: Optional[float] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class MetricDefinition:
    """Governed metric metadata; this type does not compute or verify values."""

    id: str
    metric_key: str
    display_name: str
    description: Optional[str] = None
    formula: Optional[str] = None
    source_tables: Optional[List[str]] = None
    inclusion_rules: Optional[str] = None
    exclusion_rules: Optional[str] = None
    unit: Optional[str] = None
    data_type: Optional[str] = None
    owner: Optional[str] = None
    version: Optional[int] = None
    update_frequency: Optional[str] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    validation_tests: Optional[List[JSONObject]] = None
    report_usage: Optional[List[str]] = None
    deprecation_policy: Optional[str] = None
    definition_state: Optional[str] = None
    category: Optional[str] = None
    for_stakeholder_group: Optional[str] = None
    participatory: Optional[bool] = None


@dataclass
class MetricVersion:
    """Metric definition version history record."""

    id: str
    metric_id: str
    version: int
    formula: Optional[str] = None
    changes: Optional[str] = None
    change_reason: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class MetricValue:
    """Stored metric result; computing it does not verify it."""

    id: str
    metric_id: str
    location_id: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    computation_method: Optional[str] = None
    source_record_ids: Optional[List[str]] = None
    computed_at: Optional[str] = None
    verified: Optional[bool] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    verification_notes: Optional[str] = None
    metadata: Optional[JSONObject] = None


@dataclass
class ForecastScenario:
    """Scenario definition and assumptions; does not run the forecast engine."""

    id: str
    name: str
    assumptions: JSONObject
    description: Optional[str] = None
    scenario_type: Optional[str] = None
    location_id: Optional[str] = None
    price_assumptions: Optional[JSONObject] = None
    yield_assumptions: Optional[JSONObject] = None
    cost_assumptions: Optional[JSONObject] = None
    growth_assumptions: Optional[JSONObject] = None
    version: Optional[int] = None
    parent_scenario_id: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class ForecastOutput:
    """Stored forecast result; it does not establish verification."""

    id: str
    scenario_id: str
    metric_name: str
    location_id: Optional[str] = None
    crop_cycle_id: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    confidence_low: Optional[float] = None
    confidence_high: Optional[float] = None
    confidence_level: Optional[float] = None
    calculation_version: Optional[str] = None
    calculated_at: Optional[str] = None
    inputs: Optional[JSONObject] = None
    created_by: Optional[str] = None


@dataclass
class DashboardDataset:
    """Stored dashboard dataset definition; query text is not executed here."""

    id: str
    name: str
    description: Optional[str] = None
    dataset_type: Optional[str] = None
    location_id: Optional[str] = None
    query_sql: Optional[str] = None
    refresh_interval_minutes: Optional[int] = None
    last_refreshed_at: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class TimeSeriesForecast:
    """Stored forecast series and model inputs; this record does not compute forecasts."""

    id: str
    metric_key: str
    location_id: str
    model_params: JSONObject
    forecast_values: List[JSONValue]
    prediction_intervals: JSONObject
    forecast_horizon: int
    time_unit: str
    training_points: int
    forecast_at: str
    status: TimeSeriesForecastStatus
    created_at: str
    model_type: TimeSeriesForecastModelType = "arima"
    metadata: Optional[JSONObject] = None


@dataclass
class ForecastAccuracy:
    """Stored forecast-versus-observation measurements; does not compute accuracy."""

    id: str
    forecast_id: str
    actual_timestamp: str
    predicted_value: float
    actual_value: float
    error_abs: float
    error_squared: float
    computed_at: str
    created_at: str
    error_pct: Optional[float] = None
    is_within_ci: Optional[bool] = None


@dataclass
class DemandForecast:
    """Stored demand projection; creating this value does not calculate a forecast."""

    id: str
    location_id: str
    forecast_type: DemandForecastType
    forecast_period_start: str
    forecast_period_end: str
    predicted_quantity: float
    unit: str
    status: DemandForecastStatus
    created_at: str
    updated_at: str
    crop_id: Optional[str] = None
    predicted_revenue_usd: Optional[float] = None
    confidence_low: Optional[float] = None
    confidence_high: Optional[float] = None
    confidence_level: Optional[float] = None
    seasonal_index: Optional[float] = None
    trend_slope: Optional[float] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    training_data_points: Optional[int] = None
    mape_pct: Optional[float] = None
    inputs: Optional[JSONObject] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class MarketSizeEstimate:
    """Stored TAM/SAM/SOM estimate with market scope and source fields."""

    id: str
    location_id: str
    market_scope: MarketScope
    status: MarketSizeEstimateStatus
    created_at: str
    updated_at: str
    crop_id: Optional[str] = None
    market_name: Optional[str] = None
    tam_value: Optional[float] = None
    tam_unit: Optional[str] = None
    tam_source: Optional[str] = None
    sam_value: Optional[float] = None
    sam_unit: Optional[str] = None
    sam_source: Optional[str] = None
    som_value: Optional[float] = None
    som_unit: Optional[str] = None
    som_source: Optional[str] = None
    market_penetration_pct: Optional[float] = None
    market_share_pct: Optional[float] = None
    annual_growth_rate_pct: Optional[float] = None
    growth_source: Optional[str] = None
    estimation_method: Optional[str] = None
    confidence_level: Optional[str] = None
    assessment_date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    notes: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    metadata: Optional[JSONObject] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class PriceObservation:
    """Stored market price and oracle consensus; it does not fetch or attest prices."""

    id: str
    price_date: str
    crop_id: Optional[str] = None
    commodity_code: Optional[str] = None
    market_name: Optional[str] = None
    price_per_unit: Optional[float] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    confidence: Optional[float] = None
    deviation_pct: Optional[float] = None
    source_count: Optional[int] = None
    aggregation_method: Optional[PriceAggregationMethod] = None
    source_metadata: Optional[JSONObject] = None
    market_id: Optional[str] = None
    location_id: Optional[str] = None
    buyer_type: Optional[str] = None
    quality_grade: Optional[str] = None
    quantity_traded: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    verified: Optional[bool] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class OraclePriceLog:
    """Stored oracle feed and attestation reference; it does not submit attestations."""

    id: str
    commodity: str
    price: float
    price_timestamp: str
    source: str
    currency: Optional[str] = None
    source_count: Optional[int] = None
    confidence: Optional[float] = None
    deviation_pct: Optional[float] = None
    aggregation_method: Optional[PriceAggregationMethod] = None
    attestation_uid: Optional[str] = None
    attested_at: Optional[str] = None
    chain: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None


@dataclass
class ActuationLog:
    """Stored actuation intent and result; it cannot approve, send, or execute commands."""

    id: str
    actuator_type: ActuatorType
    actuator_command: str
    command_payload: JSONObject
    trigger_source: str
    location_id: Optional[str] = None
    sensor_alert_id: Optional[str] = None
    actuator_topic: Optional[str] = None
    trigger_alert_severity: Optional[str] = None
    human_approval_required: Optional[bool] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    sent_at: Optional[str] = None
    response_received_at: Optional[str] = None
    response_payload: Optional[JSONObject] = None
    status: Optional[ActuationLogStatus] = None
    error_message: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    source_alert_event_id: Optional[str] = None


@dataclass
class SensorAnomalyEffect:
    """Durable per-reading/rule processing receipt; it does not run anomaly detection."""

    source_reading_id: str
    alert_rule_id: str
    source_event_id: str
    outcome: SensorAnomalyEffectOutcome
    created_at: str
    updated_at: str
    sensor_alert_id: Optional[str] = None
    location_id: Optional[str] = None


@dataclass
class DemandTrend:
    """Stored demand trend analysis and inputs; does not rerun its calculation."""

    id: str
    location_id: str
    analysis_type: DemandTrendAnalysisType
    period_start: str
    period_end: str
    status: DemandTrendStatus
    created_at: str
    updated_at: str
    crop_id: Optional[str] = None
    month_of_year: Optional[int] = None
    seasonal_index: Optional[float] = None
    seasonal_amplitude: Optional[float] = None
    price_elasticity: Optional[float] = None
    cross_price_elasticity: Optional[float] = None
    reference_crop_id: Optional[str] = None
    trend_direction: Optional[str] = None
    trend_slope: Optional[float] = None
    trend_r_squared: Optional[float] = None
    moving_avg_3m: Optional[float] = None
    moving_avg_6m: Optional[float] = None
    moving_avg_12m: Optional[float] = None
    avg_monthly_demand: Optional[float] = None
    peak_month: Optional[int] = None
    trough_month: Optional[int] = None
    coefficient_of_variation: Optional[float] = None
    model_name: Optional[str] = None
    data_points: Optional[int] = None
    calculation_version: Optional[str] = None
    inputs: Optional[JSONObject] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class BuyerDemandSignal:
    """Stored buyer intent/order signal; this record does not confirm fulfillment."""

    id: str
    location_id: str
    signal_type: BuyerSignalType
    signal_date: str
    currency: str
    recurring: bool
    status: BuyerSignalStatus
    created_at: str
    updated_at: str
    partner_id: Optional[str] = None
    crop_id: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_type: Optional[BuyerType] = None
    expected_delivery_start: Optional[str] = None
    expected_delivery_end: Optional[str] = None
    quantity_requested: Optional[float] = None
    unit: Optional[str] = None
    price_offered: Optional[float] = None
    recurrence_pattern: Optional[str] = None
    reliability_score: Optional[float] = None
    commitment_level: Optional[BuyerCommitmentLevel] = None
    notes: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    metadata: Optional[JSONObject] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class ProductionMarketMatch:
    """Stored production/demand comparison; does not calculate a supply gap."""

    id: str
    location_id: str
    period_start: str
    period_end: str
    status: DemandForecastStatus
    created_at: str
    updated_at: str
    crop_id: Optional[str] = None
    projected_production_tonnes: Optional[float] = None
    confirmed_supply_tonnes: Optional[float] = None
    supply_source: Optional[str] = None
    confirmed_demand_tonnes: Optional[float] = None
    pipeline_demand_tonnes: Optional[float] = None
    total_demand_tonnes: Optional[float] = None
    demand_source: Optional[str] = None
    supply_demand_gap_tonnes: Optional[float] = None
    gap_pct: Optional[float] = None
    demand_coverage_pct: Optional[float] = None
    unallocated_tonnes: Optional[float] = None
    unfulfilled_demand_tonnes: Optional[float] = None
    estimated_revenue_at_fill: Optional[float] = None
    revenue_gap_usd: Optional[float] = None
    calculation_version: Optional[str] = None
    inputs: Optional[JSONObject] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class BuyerSegment:
    """Stored buyer segment and measures; this type does not classify buyers."""

    id: str
    location_id: str
    segment_name: str
    segment_type: BuyerSegmentType
    criteria: JSONObject
    status: DemandForecastStatus
    created_at: str
    updated_at: str
    description: Optional[str] = None
    buyer_count: Optional[int] = None
    total_revenue_usd: Optional[float] = None
    avg_order_value: Optional[float] = None
    avg_payment_days: Optional[float] = None
    repeat_purchase_rate: Optional[float] = None
    growth_rate_pct: Optional[float] = None
    segment_value: Optional[BuyerSegmentValue] = None
    trend_direction: Optional[str] = None
    assessment_date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    notes: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class TrendEstimate:
    """Stored trend fit and confidence metadata; this type does not fit a trend."""

    id: str
    metric_key: str
    location_id: str
    period_start: str
    period_end: str
    data_points: int
    slope: float
    intercept: float
    r_squared: float
    standard_error: float
    direction: TrendDirection
    confidence_level: TrendConfidenceLevel
    time_unit: str
    computed_at: str
    computed_by: str
    created_at: str
    slope_p_value: Optional[float] = None
    slope_ci_lower: Optional[float] = None
    slope_ci_upper: Optional[float] = None
    metadata: Optional[JSONObject] = None


@dataclass
class TrendSmoothing:
    """Stored smoothed series value; this type does not perform smoothing."""

    id: str
    metric_key: str
    location_id: str
    smoothing_type: TrendSmoothingType
    original_value: float
    smoothed_value: float
    timestamp: str
    computed_at: str
    created_at: str
    window_size: Optional[int] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None


@dataclass
class ChangePoint:
    """Stored detected regime change and its evidence fields."""

    id: str
    metric_key: str
    location_id: str
    detection_method: ChangePointDetectionMethod
    change_point_index: int
    magnitude: float
    direction: ChangePointDirection
    confidence: float
    segment_count: int
    status: ChangePointStatus
    detected_at: str
    created_at: str
    change_point_timestamp: Optional[str] = None
    pre_mean: Optional[float] = None
    post_mean: Optional[float] = None
    pre_std: Optional[float] = None
    post_std: Optional[float] = None
    classification: Optional[str] = None
    metadata: Optional[JSONObject] = None


@dataclass
class SeasonalDecomposition:
    """Stored seasonal/trend/residual components; does not run decomposition."""

    id: str
    metric_key: str
    location_id: str
    period: int
    trend_component: List[JSONValue]
    seasonal_component: List[JSONValue]
    residual_component: List[JSONValue]
    data_points: int
    computed_at: str
    created_at: str
    decomposition_method: SeasonalDecompositionMethod = "classical"
    seasonal_strength: Optional[float] = None
    trend_strength: Optional[float] = None
    residual_variance: Optional[float] = None
    metadata: Optional[JSONObject] = None


@dataclass
class TrendDashboardMetric:
    """Stored summary metrics for trend dashboards; does not aggregate data."""

    id: str
    metric_key: str
    location_id: str
    computed_at: str
    created_at: str
    current_value: Optional[float] = None
    trend_slope: Optional[float] = None
    trend_direction: Optional[str] = None
    trend_r_squared: Optional[float] = None
    trend_significance: Optional[str] = None
    seasonal_strength: Optional[float] = None
    noise_level: Optional[float] = None
    change_point_count: int = 0
    last_change_point_at: Optional[str] = None
    forecast_next_value: Optional[float] = None
    forecast_accuracy_mae: Optional[float] = None


@dataclass
class LossEvent:
    id: str
    location_id: str
    loss_date: str
    loss_type: str
    crop_cycle_id: Optional[str] = None
    harvest_id: Optional[str] = None
    plot_id: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    estimated_value: Optional[float] = None
    cause: Optional[str] = None
    impact_description: Optional[str] = None
    mitigation: Optional[str] = None
    severity: Optional[str] = None
    evidence_urls: Optional[List[str]] = None
    evidence_hashes: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    submitted_at: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class LaborEvent:
    id: str
    location_id: str
    work_date: str
    hours_worked: float
    plot_id: Optional[str] = None
    crop_cycle_id: Optional[str] = None
    staff_id: Optional[str] = None
    worker_name: Optional[str] = None
    hourly_rate: Optional[float] = None
    total_cost: Optional[float] = None
    role: Optional[str] = None
    activity_description: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    submitted_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class FieldNote:
    id: str
    location_id: str
    note_date: str
    plot_id: Optional[str] = None
    crop_cycle_id: Optional[str] = None
    note_type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    images: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    submitted_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    schema_version: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class SensorReading:
    id: str
    location_id: str
    sensor_id: str
    reading_date: str
    value: float
    unit: str
    plot_id: Optional[str] = None
    sensor_type: Optional[str] = None
    reading_time: Optional[str] = None
    quality: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    schema_version: Optional[str] = None


@dataclass
class WeatherObservation:
    """Stored weather observation; this record does not fetch or validate provider data."""

    id: str
    location_id: str
    observation_date: str
    observation_time: Optional[str] = None
    source: Optional[str] = None
    temperature_c: Optional[float] = None
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    rainfall_mm: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    solar_radiation_wm2: Optional[float] = None
    sunshine_hours: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None
    visibility_km: Optional[float] = None
    metadata: Optional[JSONObject] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    schema_version: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class SoilSample:
    """Stored soil laboratory/field sample; creating it does not validate results."""

    id: str
    plot_id: str
    location_id: str
    sample_date: str
    sample_id: Optional[str] = None
    depth_cm: Optional[float] = None
    depth_layer: Optional[str] = None
    ph: Optional[float] = None
    organic_matter_pct: Optional[float] = None
    organic_carbon_pct: Optional[float] = None
    nitrogen_ppm: Optional[float] = None
    phosphorus_ppm: Optional[float] = None
    potassium_ppm: Optional[float] = None
    calcium_ppm: Optional[float] = None
    magnesium_ppm: Optional[float] = None
    sulfur_ppm: Optional[float] = None
    cec: Optional[float] = None
    texture: Optional[str] = None
    moisture_pct: Optional[float] = None
    lab_name: Optional[str] = None
    lab_report_url: Optional[str] = None
    evidence_hash: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    schema_version: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    evidence_maturity: Optional[int] = None
    lab_accredited: Optional[bool] = None
    analytical_method: Optional[str] = None
    protocol_id: Optional[str] = None
    composite_count: Optional[int] = None
    sub_sample_count: Optional[int] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    collector_name: Optional[str] = None
    collector_id: Optional[str] = None
    chain_of_custody: Optional[str] = None
    container_type: Optional[str] = None
    preservative: Optional[str] = None
    sample_mass_g: Optional[int] = None
    moisture_conditions: Optional[str] = None
    point_geometry: Optional[GeoJSONPoint] = None


@dataclass
class SoilCarbonMeasurement:
    """Stored soil-carbon measurement; the SDK does not calculate or verify it."""

    id: str
    plot_id: str
    location_id: str
    measurement_date: str
    carbon_pct: Optional[float] = None
    carbon_tonnes_per_ha: Optional[float] = None
    organic_carbon_stock: Optional[float] = None
    measurement_method: Optional[str] = None
    depth_cm: Optional[float] = None
    is_baseline: Optional[bool] = None
    baseline_id: Optional[str] = None
    evidence_urls: Optional[List[str]] = None
    evidence_hash: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    schema_version: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    evidence_maturity: Optional[int] = None
    lab_accredited: Optional[bool] = None
    analytical_method: Optional[str] = None
    protocol_id: Optional[str] = None


@dataclass
class EnvironmentalBaseline:
    """Stored environmental reference measurement; this record does not calculate it."""

    id: str
    location_id: str
    metric_name: str
    plot_id: Optional[str] = None
    baseline_value: Optional[float] = None
    unit: Optional[str] = None
    measurement_date: Optional[str] = None
    measurement_method: Optional[str] = None
    source: Optional[str] = None
    evidence_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    schema_version: Optional[str] = None


@dataclass
class SpeciesObservation:
    """Stored biodiversity observation; this record does not verify species claims."""

    id: str
    location_id: str
    observation_date: str
    plot_id: Optional[str] = None
    species_name: Optional[str] = None
    species_common_name: Optional[str] = None
    species_category: Optional[str] = None
    taxonomic_family: Optional[str] = None
    count: Optional[int] = None
    abundance: Optional[str] = None
    observer: Optional[str] = None
    observer_id: Optional[str] = None
    method: Optional[str] = None
    habitat_type: Optional[str] = None
    evidence_urls: Optional[List[str]] = None
    evidence_hashes: Optional[List[str]] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    schema_version: Optional[str] = None
    trophic_level: Optional[TrophicLevel] = None
    population_density_per_m2: Optional[float] = None
    conservation_status: Optional[ConservationStatus] = None
    status: Optional[LifecycleStatus] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    evidence_maturity: Optional[int] = None


@dataclass
class RemoteSensingObservation:
    """Stored satellite/drone observation; this record does not fetch imagery or compute indices."""

    id: str
    location_id: str
    observation_date: str
    plot_id: Optional[str] = None
    source: Optional[str] = None
    ndvi: Optional[float] = None
    ndre: Optional[float] = None
    evi: Optional[float] = None
    savi: Optional[float] = None
    canopy_cover_pct: Optional[float] = None
    canopy_height_m: Optional[float] = None
    ndwi: Optional[float] = None
    bbox: Optional[GeoJSONPolygon] = None
    centroid: Optional[GeoJSONPoint] = None
    cloud_cover_pct: Optional[float] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    schema_version: Optional[str] = None
    msavi: Optional[float] = None
    satvi: Optional[float] = None
    bsi: Optional[float] = None
    nbr2: Optional[float] = None
    ndti: Optional[float] = None
    lswi: Optional[float] = None
    brightness_index: Optional[float] = None
    tc_brightness: Optional[float] = None
    tc_greenness: Optional[float] = None
    tc_wetness: Optional[float] = None
    band_blue: Optional[float] = None
    band_green: Optional[float] = None
    band_red: Optional[float] = None
    band_nir: Optional[float] = None
    band_swir1: Optional[float] = None
    band_swir2: Optional[float] = None


@dataclass
class MrvClaim:
    """Stored MRV claim and evidence links; it does not verify or attest the claim."""

    id: str
    location_id: str
    claim_type: str
    claim_date: str
    claim_data: JSONObject
    created_at: Optional[str] = None
    plot_id: Optional[str] = None
    source_record_ids: Optional[List[str]] = None
    evidence_urls: Optional[List[str]] = None
    evidence_hashes: Optional[List[str]] = None
    status: Optional[LifecycleStatus] = None
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[str] = None
    attestation_uid: Optional[str] = None
    attested_at: Optional[str] = None
    schema_version: Optional[str] = None
    created_by: Optional[str] = None
    sensor_device_id: Optional[str] = None
    sensor_alert_id: Optional[str] = None
    source_readings: Optional[List[str]] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    evidence_maturity: Optional[int] = None
    external_verifier: Optional[str] = None
    methodology_ref: Optional[str] = None
    public_claim: Optional[bool] = None
    source_sensor_reading_event_id: Optional[str] = None


@dataclass
class VerificationReview:
    """Stored human verification review; recording it does not change claim lifecycle."""

    id: str
    claim_id: str
    reviewer_id: str
    review_date: str
    result: str
    method: Optional[str] = None
    notes: Optional[str] = None
    evidence_urls: Optional[List[str]] = None
    created_at: Optional[str] = None


@dataclass
class SensorType:
    id: str
    name: str
    unit: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class SensorDevice:
    id: str
    name: str
    slug: str
    sensor_type_id: str
    location_id: str
    plot_id: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    protocol: Optional[str] = None
    endpoint_url: Optional[str] = None
    status: Optional[EntityStatusExtended] = None
    calibration_date: Optional[str] = None
    calibration_interval_days: Optional[int] = None
    installation_date: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    elevation_m: Optional[float] = None
    point_geometry: Optional[GeoJSONPoint] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class AlertRule:
    id: str
    name: str
    sensor_type_id: str
    metric: str
    operator: str
    threshold_value: float
    threshold_value_max: Optional[float] = None
    severity: Optional[str] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None
    auto_create_claim: Optional[bool] = None
    claim_type: Optional[str] = None
    actuator_enabled: Optional[bool] = None
    actuator_type: Optional[ActuatorType] = None
    actuator_command: Optional[str] = None
    actuator_topic: Optional[str] = None
    human_approval_required: Optional[bool] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class SensorAlert:
    id: str
    sensor_device_id: str
    alert_rule_id: str
    severity: SensorSeverity
    message: str
    triggered_at: str
    location_id: Optional[str] = None
    reading_id: Optional[str] = None
    status: Optional[AlertLifecycle] = None
    reading_value: Optional[float] = None
    threshold_value: Optional[float] = None
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[str] = None
    claim_id: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    actuation_sent: Optional[bool] = None
    actuation_response: Optional[JSONObject] = None
    actuation_status: Optional[ActuationStatus] = None


@dataclass
class Protocol:
    """Stored Web3 protocol catalog entry; this record does not submit transactions."""

    id: str
    name: str
    slug: str
    chain: str
    contract_address: Optional[str] = None
    protocol_type: Optional[str] = None
    category: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None


@dataclass
class WalletProfile:
    id: str
    address: str
    chain: str
    chain_id: Optional[int] = None
    role: Optional[str] = None
    owner_type: Optional[str] = None
    owner_id: Optional[str] = None
    label: Optional[str] = None
    is_active: Optional[bool] = None
    first_seen_date: Optional[str] = None
    last_active_date: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class AttestationSchema:
    """Stored EAS schema catalog entry; it does not create or submit attestations."""

    id: str
    schema_uid: str
    name: str
    chain: str
    description: Optional[str] = None
    schema_text: Optional[str] = None
    resolver_address: Optional[str] = None
    version: Optional[int] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None


@dataclass
class AttestationRecord:
    id: str
    schema_id: str
    claim_data: JSONObject
    attestation_uid: Optional[str] = None
    claim_type: Optional[str] = None
    subject_id: Optional[str] = None
    subject_type: Optional[str] = None
    evidence_hash: Optional[str] = None
    evidence_cids: Optional[List[str]] = None
    evidence_urls: Optional[List[str]] = None
    status: Optional[LifecycleStatus] = None
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[str] = None
    chain: Optional[str] = None
    tx_hash: Optional[str] = None
    attested_at: Optional[str] = None
    expiration_date: Optional[str] = None
    revocation_date: Optional[str] = None
    schema_version: Optional[str] = None
    expires_at: Optional[str] = None
    evaluator_id: Optional[str] = None
    private_payload_hash: Optional[str] = None
    payload_cid: Optional[str] = None
    verdict: Optional[AttestationVerdict] = None
    rationale: Optional[str] = None
    evidence_reviewed: Optional[List[str]] = None
    graph_iri: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class ReportSnapshot:
    id: str
    report_name: str
    report_data: JSONObject
    report_type: Optional[str] = None
    location_id: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    snapshot_hash: Optional[str] = None
    file_url: Optional[str] = None
    status: Optional[LifecycleStatus] = None
    frozen: Optional[bool] = None
    frozen_at: Optional[str] = None
    frozen_by: Optional[str] = None
    public_interest_summary: Optional[str] = None
    uncertainty_notes: Optional[str] = None
    negative_findings: Optional[List[JSONObject]] = None
    affected_community_voice: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class AiSummary:
    """Stored agent narrative with source lineage and human review state."""

    id: str
    subject_type: str
    subject_id: str
    content: str
    summary_type: Optional[str] = None
    source_record_ids: Optional[List[str]] = None
    source_tables: Optional[List[str]] = None
    model_version: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[LifecycleStatus] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class ExportLog:
    id: str
    export_type: str
    format: Optional[str] = None
    entity_type: Optional[str] = None
    entity_ids: Optional[List[str]] = None
    user_id: Optional[str] = None
    target_table: Optional[str] = None
    filters: Optional[JSONObject] = None
    row_count: Optional[int] = None
    file_size_bytes: Optional[int] = None
    file_url: Optional[str] = None
    status: Optional[ExportStatus] = None
    created_at: Optional[str] = None


@dataclass
class CashFlowSnapshot:
    """Stored cash-flow summary; this record does not calculate or reconcile balances."""

    id: str
    location_id: str
    period_start: str
    period_end: str
    total_revenue: Optional[float] = None
    capital_inflows: Optional[float] = None
    grants_received: Optional[float] = None
    total_inflows: Optional[float] = None
    total_operating_expenses: Optional[float] = None
    total_capex: Optional[float] = None
    loan_repayments: Optional[float] = None
    public_goods_allocation: Optional[float] = None
    total_outflows: Optional[float] = None
    net_cash_flow: Optional[float] = None
    running_balance: Optional[float] = None
    calculation_version: Optional[str] = None
    calculated_at: Optional[str] = None
    inputs: Optional[JSONObject] = None
    created_by: Optional[str] = None


@dataclass
class NoiSnapshot:
    id: str
    crop_cycle_id: str
    location_id: str
    period_start: str
    period_end: str
    gross_revenue: Optional[float] = None
    returns_and_discounts: Optional[float] = None
    net_revenue: Optional[float] = None
    direct_crop_costs: Optional[float] = None
    allocated_shared_costs: Optional[float] = None
    total_costs: Optional[float] = None
    noi: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    loss_rate_pct: Optional[float] = None
    calculation_version: Optional[str] = None
    calculated_at: Optional[str] = None
    inputs: Optional[JSONObject] = None
    created_by: Optional[str] = None


@dataclass
class CarbonCredit:
    """Read model for a governed credit; lifecycle actions use reviewed services."""

    id: str
    location_id: str
    credit_code: str
    vintage_year: int
    methodology: str
    initial_sequestration_tonnes: Decimal
    current_sequestration_tonnes: Decimal
    issuable_tonnes: Decimal
    farm_id: Optional[str] = None
    methodology_version: Optional[str] = None
    adjustment_margin_pct: Optional[Decimal] = None
    buffer_pool_pct: Optional[Decimal] = None
    retired_tonnes: Optional[Decimal] = None
    available_tonnes: Optional[Decimal] = None
    price_per_tonne_usd: Optional[Decimal] = None
    market_price_per_tonne_usd: Optional[Decimal] = None
    effective_price_per_tonne_usd: Optional[Decimal] = None
    total_value_usd: Optional[Decimal] = None
    climate_impact_summary_id: Optional[str] = None
    evidence_maturity: Optional[int] = None
    external_verifier: Optional[str] = None
    methodology_ref: Optional[str] = None
    attestation_uid: Optional[str] = None
    attestation_schema_id: Optional[str] = None
    attested_at: Optional[str] = None
    token_chain: Optional[str] = None
    token_contract: Optional[str] = None
    token_id: Optional[str] = None
    token_minted_at: Optional[str] = None
    status: Optional[CarbonCreditStatus] = None
    reviewer_id: Optional[str] = None
    review_date: Optional[str] = None
    review_notes: Optional[str] = None
    metadata: Optional[JSONObject] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    source_raw: Optional[JSONObject] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    credit_class_id: Optional[str] = None
    credit_batch_id: Optional[str] = None
    expires_at: Optional[str] = None
    reserved_tonnes: Optional[Decimal] = None


@dataclass
class CreditAdjustment:
    """Append-oriented credit adjustment review record."""

    id: str
    credit_id: str
    location_id: str
    adjustment_type: CreditAdjustmentType
    previous_sequestration_tonnes: Decimal
    new_sequestration_tonnes: Decimal
    delta_tonnes: Decimal
    delta_pct: Decimal
    trigger_source: CreditAdjustmentTriggerSource
    within_margin: bool
    requires_review: bool
    trigger_record_id: Optional[str] = None
    trigger_snapshot: Optional[JSONObject] = None
    reviewer_id: Optional[str] = None
    review_date: Optional[str] = None
    review_result: Optional[str] = None
    review_notes: Optional[str] = None
    adjustment_attestation_uid: Optional[str] = None
    adjustment_attested_at: Optional[str] = None
    status: Optional[CreditAdjustmentStatus] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class CreditRetirement:
    """Read model for a retirement request and its separate review state."""

    id: str
    credit_id: str
    location_id: str
    retirement_reason: str
    retired_tonnes: Decimal
    beneficiary_name: Optional[str] = None
    beneficiary_wallet: Optional[str] = None
    retirement_statement: Optional[str] = None
    retirement_value_usd: Optional[Decimal] = None
    evidence_cid: Optional[str] = None
    evidence_hash: Optional[str] = None
    retirement_attestation_uid: Optional[str] = None
    retired_onchain_at: Optional[str] = None
    retirement_tx_hash: Optional[str] = None
    status: Optional[CreditRetirementStatus] = None
    reviewer_id: Optional[str] = None
    review_date: Optional[str] = None
    review_notes: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    expires_at: Optional[str] = None
    idempotency_key: Optional[str] = None
    confirmed_at: Optional[str] = None
    cancelled_at: Optional[str] = None


@dataclass
class CreditTransfer:
    """Read model for a credit transfer ledger entry."""

    id: str
    credit_id: str
    location_id: str
    transfer_type: CreditTransferType
    transferred_tonnes: Decimal
    transfer_value_usd: Optional[Decimal] = None
    price_per_tonne_usd: Optional[Decimal] = None
    from_wallet: Optional[str] = None
    to_wallet: Optional[str] = None
    from_entity: Optional[str] = None
    to_entity: Optional[str] = None
    revenue_event_id: Optional[str] = None
    treasury_event_id: Optional[str] = None
    evidence_cid: Optional[str] = None
    evidence_hash: Optional[str] = None
    tx_hash: Optional[str] = None
    chain: Optional[str] = None
    status: Optional[CreditTransferStatus] = None
    reviewer_id: Optional[str] = None
    review_date: Optional[str] = None
    review_notes: Optional[str] = None
    metadata: Optional[JSONObject] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
