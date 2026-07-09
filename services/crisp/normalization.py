"""Normalization helpers for CRISP 0-100 risk scores."""

from __future__ import annotations


def clamp_risk_score(value: float) -> float:
    """Clamp any numeric score into the CRISP 0-100 range."""
    return round(max(0.0, min(100.0, float(value))), 2)


def normalize_to_risk(value: float, minimum: float, maximum: float, invert: bool = False) -> float:
    """Normalize a raw value into a 0-100 risk score.

    Higher output = higher risk.  Use invert=True when a higher raw value
    means *lower* risk (e.g. yield likelihood).
    """
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")
    ratio = (float(value) - minimum) / (maximum - minimum)
    if invert:
        ratio = 1 - ratio
    return clamp_risk_score(ratio * 100)


def likelihood_to_risk_score(likelihood: float) -> float:
    """Convert a 0-1 likelihood (1 = extremely likely to yield) to a 0-100 risk score."""
    return clamp_risk_score((1 - likelihood) * 100)


def hazard_score_to_risk(hazard_total: float, max_hazard: float = 15.0) -> float:
    """Convert a summed hazard rating (0-max_hazard) to a 0-100 risk score."""
    if max_hazard <= 0:
        raise ValueError("max_hazard must be positive")
    return clamp_risk_score((hazard_total / max_hazard) * 100)


def weighted_average_risk(scores: dict, weights: dict) -> float:
    """Compute weighted average of risk scores.

    Args:
        scores: {dimension_key: risk_score (0-100)}
        weights: {dimension_key: weight (0-1)}

    Returns:
        Weighted average risk score (0-100).
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for key, score in scores.items():
        w = weights.get(key, 0.0)
        if w > 0 and score is not None:
            weighted_sum += score * w
            total_weight += w
    if total_weight == 0:
        return 0.0
    return clamp_risk_score(weighted_sum / total_weight)
