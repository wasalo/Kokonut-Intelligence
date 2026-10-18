from __future__ import annotations

from dataclasses import dataclass
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
ActuationStatus = Literal[
    "pending", "sent", "acknowledged", "executed", "failed", "requires_approval"
]
AttestationVerdict = Literal["pending", "approved", "rejected", "needs_info"]

GeoJSONPosition = List[float]


class GeoJSONPoint(TypedDict):
    """GeoJSON point returned for PostGIS POINT columns."""

    type: Literal["Point"]
    coordinates: GeoJSONPosition


class GeoJSONPolygon(TypedDict):
    """GeoJSON polygon returned for PostGIS POLYGON columns."""

    type: Literal["Polygon"]
    coordinates: List[List[GeoJSONPosition]]


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
