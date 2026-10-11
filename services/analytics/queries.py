"""Kokonut-owned analytics query contracts, independent of database drivers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol


class QueryId(str, Enum):
    PUBLIC_METRIC_SUMMARY = "public_metric_summary"


@dataclass(frozen=True)
class AnalyticsContext:
    """Scope supplied by the application boundary, never by arbitrary SQL."""

    location_id: str
    public: bool = True


@dataclass(frozen=True)
class MetricSummaryRequest:
    location_id: str


@dataclass(frozen=True)
class MetricSummary:
    metric_key: str
    display_name: str
    unit: str | None
    value: Decimal | float | int | None
    computed_at: datetime | None

    def to_dict(self) -> dict:
        return {
            "metric_key": self.metric_key,
            "display_name": self.display_name,
            "unit": self.unit,
            "value": self.value,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }


class AnalyticsBackend(Protocol):
    def execute(
        self, query_id: QueryId, request: MetricSummaryRequest, context: AnalyticsContext
    ) -> tuple[MetricSummary, ...]: ...
