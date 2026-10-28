"""Explicit response contracts for private produce traceability reads."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def _json_decimal(value: Decimal) -> int | float:
    """Match FastAPI's legacy Decimal encoder for the existing wire contract."""
    if value.as_tuple().exponent >= 0:
        return int(value)
    return float(value)


JsonDecimal = Annotated[
    Decimal,
    PlainSerializer(_json_decimal, return_type=int | float, when_used="json"),
]
JsonDateTime = Annotated[
    datetime,
    PlainSerializer(lambda value: value.isoformat(), return_type=str, when_used="json"),
]


class _TraceabilityModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )


class TraceabilityBatchPageItem(_TraceabilityModel):
    id: UUID
    batch_number: str
    crop_name: str
    variety: str | None
    quantity: JsonDecimal
    unit: str | None
    harvest_date: date
    organic: bool | None
    status: Literal["active", "in_transit", "delivered", "consumed", "rejected", "expired"]
    created_at: JsonDateTime


class TraceabilityBatchPage(_TraceabilityModel):
    location_id: UUID
    items: list[TraceabilityBatchPageItem] = Field(max_length=50)
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=10_000)
    has_more: bool


class TraceabilityBatch(_TraceabilityModel):
    id: UUID
    batch_number: str
    crop_name: str
    variety: str | None
    quantity: JsonDecimal
    unit: str | None
    harvest_date: date
    organic: bool | None
    status: Literal["active", "in_transit", "delivered", "consumed", "rejected", "expired"]
    expiry_date: date | None
    grade: str | None


class TraceabilityCustodyTransfer(_TraceabilityModel):
    sequence_num: int
    from_actor_type: str
    to_actor_type: str
    transfer_date: JsonDateTime
    received_date: JsonDateTime | None
    quantity: JsonDecimal
    unit: str | None
    transfer_method: str | None
    temperature_at_transfer_c: JsonDecimal | None
    status: Literal["pending", "in_transit", "received", "rejected", "cancelled"]


class TraceabilityQualityInspection(_TraceabilityModel):
    inspection_date: JsonDateTime
    inspection_point: Literal[
        "harvest", "receiving", "processing", "pre_dispatch", "delivery", "retail"
    ]
    overall_grade: str | None
    score: JsonDecimal | None
    moisture_pct: JsonDecimal | None
    foreign_material_pct: JsonDecimal | None
    temperature_c: JsonDecimal | None
    appearance_score: JsonDecimal | None
    freshness_score: JsonDecimal | None
    size_uniformity: JsonDecimal | None
    defect_count: int | None
    passed: bool
    status: Literal["recorded", "reviewed", "escalated", "closed"]


class TraceabilityCertification(_TraceabilityModel):
    certification: str
    category: str | None
    issued_date: date
    expiry_date: date | None
    verified: bool | None
    chain_verified: bool | None
    status: Literal["pending", "verified", "expired", "revoked", "suspended"]


class TraceabilityFoodSafetyRecord(_TraceabilityModel):
    record_type: Literal[
        "temperature_log", "hygiene_check", "pest_control", "cleaning_log",
        "allergen_check", "haccp", "other",
    ]
    record_time: JsonDateTime
    temperature_c: JsonDecimal | None
    temperature_min_c: JsonDecimal | None
    temperature_max_c: JsonDecimal | None
    within_range: bool | None
    humidity_pct: JsonDecimal | None
    ph_level: JsonDecimal | None
    hygiene_score: JsonDecimal | None
    hand_wash_ok: bool | None
    protective_gear_ok: bool | None
    pest_detected: bool | None
    passed: bool
    status: Literal["recorded", "reviewed", "escalated", "closed"]


class TraceabilityProvenanceEvent(_TraceabilityModel):
    event_type: str
    event_time: JsonDateTime
    chain_verified: bool | None
    status: Literal["recorded", "verified", "disputed"]


class TraceabilityCustodyTransfers(_TraceabilityModel):
    items: list[TraceabilityCustodyTransfer] = Field(max_length=100)
    truncated: bool


class TraceabilityQualityInspections(_TraceabilityModel):
    items: list[TraceabilityQualityInspection] = Field(max_length=100)
    truncated: bool


class TraceabilityCertifications(_TraceabilityModel):
    items: list[TraceabilityCertification] = Field(max_length=100)
    truncated: bool


class TraceabilityFoodSafetyRecords(_TraceabilityModel):
    items: list[TraceabilityFoodSafetyRecord] = Field(max_length=100)
    truncated: bool


class TraceabilityProvenanceEvents(_TraceabilityModel):
    items: list[TraceabilityProvenanceEvent] = Field(max_length=100)
    truncated: bool


class TraceabilityBatchDetail(_TraceabilityModel):
    location_id: UUID
    batch: TraceabilityBatch
    custody_transfers: TraceabilityCustodyTransfers
    quality_inspections: TraceabilityQualityInspections
    certifications: TraceabilityCertifications
    food_safety_records: TraceabilityFoodSafetyRecords
    provenance_events: TraceabilityProvenanceEvents
