"""
Risk-Adjusted Forecast Module

Applies risk factors to base forecasts to produce risk-adjusted
estimates with confidence intervals.
"""

from typing import Dict, Any, Tuple
from .models import ScenarioAssumptions


# Risk factors by scenario type
RISK_FACTORS = {
    "baseline": 0.85,
    "optimistic": 0.85,
    "conservative": 0.75,
    "custom": 0.80,
}


def calculate_risk_factor(
    scenario_type: str,
    drought_probability: float = 0.0,
    price_volatility: float = 0.10,
) -> float:
    """Calculate composite risk factor."""
    base = RISK_FACTORS.get(scenario_type, 0.80)

    # Drought reduces NOI more aggressively
    drought_penalty = drought_probability * 0.3

    # Price volatility reduces confidence
    volatility_penalty = price_volatility * 0.2

    return max(0.4, base - drought_penalty - volatility_penalty)


def calculate_confidence_interval(
    point_estimate: float,
    risk_factor: float,
    confidence_level: float = 0.80,
) -> Tuple[float, float]:
    """Calculate confidence interval around a point estimate."""
    # Standard deviation proxy based on risk factor
    std_proxy = point_estimate * (1 - risk_factor) * 0.5

    # z-score for confidence level (approximate)
    z_scores = {0.70: 1.04, 0.75: 1.15, 0.80: 1.28, 0.85: 1.44, 0.90: 1.65, 0.95: 1.96}
    z = z_scores.get(confidence_level, 1.28)

    margin = z * std_proxy
    low = max(0, point_estimate - margin)
    high = point_estimate + margin

    return round(low, 2), round(high, 2)


def risk_adjust_noi(
    base_noi: float,
    risk_factor: float,
) -> Dict[str, Any]:
    """Apply risk adjustment to NOI forecast."""
    adjusted = base_noi * risk_factor
    low, high = calculate_confidence_interval(adjusted, risk_factor)
    return {
        "base_noi": base_noi,
        "risk_factor": risk_factor,
        "risk_adjusted_noi": round(adjusted, 2),
        "confidence_low": low,
        "confidence_high": high,
    }


def risk_adjust_revenue(
    base_revenue: float,
    risk_factor: float,
) -> Dict[str, Any]:
    """Apply risk adjustment to revenue forecast."""
    adjusted = base_revenue * risk_factor
    low, high = calculate_confidence_interval(adjusted, risk_factor)
    return {
        "base_revenue": base_revenue,
        "risk_factor": risk_factor,
        "risk_adjusted_revenue": round(adjusted, 2),
        "confidence_low": low,
        "confidence_high": high,
    }
