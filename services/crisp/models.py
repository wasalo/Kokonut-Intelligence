"""CRISP risk scoring data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DimensionScore:
    """Score for a single CRISP risk dimension."""
    dimension_key: str
    dimension_name: str
    risk_score: float
    confidence_level: str
    evidence_maturity_level: int
    weight: float
    factors: Dict[str, Any] = field(default_factory=dict)
    evidence_summary: Optional[str] = None
    uncertainty_notes: Optional[str] = None


@dataclass
class CompositeRating:
    """Composite CRISP rating across all five dimensions."""
    location_id: str
    period_start: str
    period_end: str
    carbon_yield_score: Optional[float] = None
    climate_score: Optional[float] = None
    policy_score: Optional[float] = None
    financial_score: Optional[float] = None
    implementation_score: Optional[float] = None
    composite_score: Optional[float] = None
    rating: Optional[str] = None
    confidence_level: Optional[str] = None
    methodology_version: Optional[str] = None
    weights: Dict[str, float] = field(default_factory=dict)
    dimensions: List[DimensionScore] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location_id": self.location_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "carbon_yield_score": self.carbon_yield_score,
            "climate_score": self.climate_score,
            "policy_score": self.policy_score,
            "financial_score": self.financial_score,
            "implementation_score": self.implementation_score,
            "composite_score": self.composite_score,
            "rating": self.rating,
            "confidence_level": self.confidence_level,
            "methodology_version": self.methodology_version,
            "weights": self.weights,
            "dimensions": [
                {
                    "dimension_key": d.dimension_key,
                    "dimension_name": d.dimension_name,
                    "risk_score": d.risk_score,
                    "confidence_level": d.confidence_level,
                    "weight": d.weight,
                    "factors": d.factors,
                }
                for d in self.dimensions
            ],
        }
