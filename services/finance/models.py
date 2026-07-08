"""Finance models: dataclasses for financial analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CashFlowSeries:
    """A series of periodic cash flows for IRR/NPV computation."""
    cash_flows: list[float]
    discount_rate: float = 0.08
    periods: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.periods:
            self.periods = [f"Period {i}" for i in range(len(self.cash_flows))]
        if not self.labels:
            self.labels = [f"Period {i}" for i in range(len(self.cash_flows))]

    @property
    def initial_investment(self) -> float:
        """Initial investment (first cash flow, expected negative)."""
        return abs(self.cash_flows[0]) if self.cash_flows else 0

    @property
    def total_returns(self) -> float:
        """Sum of all positive cash flows."""
        return sum(cf for cf in self.cash_flows if cf > 0)

    @property
    def net_value(self) -> float:
        """Net value (sum of all cash flows)."""
        return sum(self.cash_flows)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "periods": [
                {"period": i, "date": p, "cash_flow": round(cf, 2), "label": l}
                for i, (p, cf, l) in enumerate(zip(self.periods, self.cash_flows, self.labels))
            ],
            "discount_rate_pct": round(self.discount_rate * 100, 2),
            "initial_investment": round(self.initial_investment, 2),
            "total_returns": round(self.total_returns, 2),
            "net_value": round(self.net_value, 2),
        }


@dataclass
class InvestmentMetrics:
    """Computed investment analysis metrics."""
    irr_pct: float | None = None
    npv_usd: float = 0
    mirr_pct: float | None = None
    payback_periods: float | None = None
    roi_pct: float = 0
    discount_rate_pct: float = 8.0
    total_investment_usd: float = 0
    total_return_usd: float = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "irr_pct": round(self.irr_pct, 4) if self.irr_pct is not None else None,
            "npv_usd": round(self.npv_usd, 2),
            "mirr_pct": round(self.mirr_pct, 4) if self.mirr_pct is not None else None,
            "payback_periods": round(self.payback_periods, 2) if self.payback_periods is not None else None,
            "roi_pct": round(self.roi_pct, 2),
            "discount_rate_pct": round(self.discount_rate_pct, 2),
            "total_investment_usd": round(self.total_investment_usd, 2),
            "total_return_usd": round(self.total_return_usd, 2),
        }
