"""
Revenue Multiplier Data Models

Dataclasses for opportunity dimensions and the overall multiplier map.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class OpportunityDimension:
    """A single revenue multiplier opportunity."""
    dimension_id: str
    dimension_name: str
    score: float               # 0-100
    impact_usd: float          # estimated annual USD impact
    confidence: str            # high, medium, low
    current_state: str         # what exists today
    recommendation: str        # what to do
    data_points: int           # records supporting this
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RevenueMultiplierMap:
    """Complete opportunity map for a location."""
    location_id: str
    location_name: str
    dimensions: List[OpportunityDimension]
    total_opportunity_usd: float
    overall_score: float       # weighted average across dimensions
    generated_at: str
