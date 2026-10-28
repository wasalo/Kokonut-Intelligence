"""Explicit response contract for the aggregate credit-custody read."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _CreditCustodyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreditCustodyTotals(_CreditCustodyModel):
    issuable_tonnes: str
    retired_tonnes: str
    reserved_tonnes: str
    available_tonnes: str
    recorded_total_value_usd: str


class CreditRetirementStatusSummary(_CreditCustodyModel):
    status: str
    count: int = Field(ge=0)
    requested_tonnes: str
    requested_value_usd: str


class CreditCustodySummaryResponse(_CreditCustodyModel):
    location_id: UUID
    total_credits: int = Field(ge=0)
    credit_totals: CreditCustodyTotals
    retirements_by_status: list[CreditRetirementStatusSummary]
