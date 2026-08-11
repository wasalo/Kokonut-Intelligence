"""Normalization helpers for EBF 0-10 scores and generic weighted scores."""

from __future__ import annotations

from typing import Mapping


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Clamp a numeric value into ``[minimum, maximum]`` (no rounding)."""
    return max(minimum, min(maximum, float(value)))


def clamp_score(value: float) -> float:
    """Clamp any numeric score into the EBF 0-10 range."""
    return round(clamp(value, 0, 10), 1)


def weighted_score(components: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Combine sub-scores with the given weights.

    ``weights`` must cover exactly the keys present in ``components``; the
    caller decides any rounding. Used by analytics scores (e.g. IPM
    compliance) instead of hand-rolled ``0.25 * a + 0.25 * b + ...`` sums.
    """
    unknown = set(components) - set(weights)
    if unknown:
        raise ValueError(f"No weight provided for component(s): {sorted(unknown)}")
    missing = set(weights) - set(components)
    if missing:
        raise ValueError(f"No value provided for weight key(s): {sorted(missing)}")
    return sum(weights[key] * float(components[key]) for key in weights)


def normalize_linear(value: float, minimum: float, maximum: float, invert: bool = False) -> float:
    """Normalize a raw value into a 0-10 score using a linear benchmark range."""
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")
    ratio = (float(value) - minimum) / (maximum - minimum)
    if invert:
        ratio = 1 - ratio
    return clamp_score(ratio * 10)


def normalize_percentage(value: float) -> float:
    """Normalize a 0-100 percentage into a 0-10 score."""
    return normalize_linear(value, 0, 100)
