from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
            params["page"] = (self.offset // self.limit) + 1
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
    baseline_assumptions: Optional[Dict[str, Any]] = None
    baseline_source: Optional[str] = None
    baseline_date: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class Farm:
    id: str
    location_id: str
    name: str
    slug: str
    description: Optional[str] = None
    farm_type: Optional[str] = None
    total_area: Optional[float] = None
    area_unit: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


@dataclass
class Plot:
    id: str
    farm_id: str
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    area: Optional[float] = None
    area_unit: Optional[str] = None
    soil_type: Optional[str] = None
    water_source: Optional[str] = None
    elevation_m: Optional[float] = None
    slope_pct: Optional[float] = None
    aspect: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


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
    metadata: Optional[Dict[str, Any]] = None
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
    notes: Optional[str] = None
    status: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    created_at: Optional[str] = None
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
    payment_status: Optional[str] = None
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    invoice_number: Optional[str] = None
    return_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    net_amount: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    created_at: Optional[str] = None
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
    subcategory: Optional[str] = None
    description: Optional[str] = None
    vendor: Optional[str] = None
    vendor_id: Optional[str] = None
    currency: Optional[str] = None
    is_capex: Optional[bool] = None
    allocation_method: Optional[str] = None
    allocation_weight: Optional[float] = None
    invoice_number: Optional[str] = None
    receipt_hash: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
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
    metadata: Optional[Dict[str, Any]] = None
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
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class AttestationRecord:
    id: str
    schema_id: str
    claim_data: Dict[str, Any]
    attestation_uid: Optional[str] = None
    claim_type: Optional[str] = None
    subject_id: Optional[str] = None
    subject_type: Optional[str] = None
    evidence_hash: Optional[str] = None
    status: Optional[str] = None
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[str] = None
    chain: Optional[str] = None
    tx_hash: Optional[str] = None
    attested_at: Optional[str] = None
    expiration_date: Optional[str] = None
    revocation_date: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class ReportSnapshot:
    id: str
    report_name: str
    report_data: Dict[str, Any]
    report_type: Optional[str] = None
    location_id: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    snapshot_hash: Optional[str] = None
    file_url: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class ExportLog:
    id: str
    export_type: str
    user_id: Optional[str] = None
    target_table: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    row_count: Optional[int] = None
    file_size_bytes: Optional[int] = None
    file_url: Optional[str] = None
    status: Optional[str] = None
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
    inputs: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
