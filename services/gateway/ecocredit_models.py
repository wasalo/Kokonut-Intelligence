"""Explicit response contract for location-scoped ecocredit batch reads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _EcocreditModel(BaseModel):
    # Ignore future/internal service fields so they cannot silently become API
    # fields. Declared fields remain validated by FastAPI's response pipeline.
    model_config = ConfigDict(extra="ignore")


class LocationEcocreditBatch(_EcocreditModel):
    id: UUID
    credit_class_id: UUID
    class_name: str
    credit_type: str
    class_status: str
    batch_code: str
    vintage_year: int
    unit: str | None
    batch_status: str
    total_quantity: str
    issued_quantity: str
    retired_quantity: str
    cancelled_quantity: str
    available_quantity: str
    ledger_tradable_supply: str
    ledger_retired_supply: str
    ledger_escrowed_supply: str
    created_at: datetime | None


class LocationEcocreditBatchesResponse(_EcocreditModel):
    data: list[LocationEcocreditBatch] = Field(max_length=100)
    location_id: UUID
