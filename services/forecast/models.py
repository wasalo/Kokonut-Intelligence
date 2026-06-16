"""
Forecast Data Models

Dataclasses for scenario assumptions, forecast inputs, and outputs.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal


@dataclass
class PriceAssumptions:
    maize_per_tonne_usd: float = 280.0
    cassava_per_tonne_usd: float = 180.0
    beans_per_tonne_usd: float = 650.0
    sweet_potato_per_tonne_usd: float = 220.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PriceAssumptions":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class YieldAssumptions:
    maize_yield_tonne_ha: float = 2.8
    cassava_yield_tonne_ha: float = 7.5
    beans_yield_tonne_ha: float = 1.1
    sweet_potato_yield_tonne_ha: float = 5.5

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "YieldAssumptions":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CostAssumptions:
    fertilizer_usd_per_ha: float = 120.0
    seeds_usd_per_ha: float = 80.0
    labor_usd_per_ha: float = 200.0
    irrigation_usd_per_ha: float = 60.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CostAssumptions":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class GrowthAssumptions:
    area_growth_pct: float = 0.10
    yield_improvement_pct: float = 0.05
    price_appreciation_pct: float = 0.08

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GrowthAssumptions":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ScenarioAssumptions:
    period: str = ""
    inflation_rate: float = 0.05
    exchange_rate_usd_kes: float = 155.0
    discount_rate: float = 0.12
    drought_probability: float = 0.0
    retention_rate_pct: Optional[float] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScenarioAssumptions":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CropArea:
    crop_name: str
    crop_id: str
    area_hectares: float
    yield_per_ha: float
    price_per_tonne: float


@dataclass
class HistoricalData:
    """Aggregated historical data for a location."""
    total_revenue: float = 0.0
    total_costs: float = 0.0
    total_harvest_tonnes: float = 0.0
    total_area_ha: float = 0.0
    loss_rate: float = 0.0
    avg_ndvi: float = 0.0
    soil_organic_matter: float = 0.0
    crop_areas: List[CropArea] = field(default_factory=list)


@dataclass
class ForecastResult:
    """A single forecast output metric."""
    metric_name: str
    value: float
    unit: str
    confidence_low: float
    confidence_high: float
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NOIResult:
    """Net Operating Income calculation result."""
    gross_revenue: float
    returns_and_discounts: float
    net_revenue: float
    direct_crop_costs: float
    allocated_shared_costs: float
    total_costs: float
    noi: float
    operating_margin_pct: float
    loss_rate_pct: float
    inputs: Dict[str, Any] = field(default_factory=dict)
