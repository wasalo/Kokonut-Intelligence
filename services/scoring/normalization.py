"""Normalization helpers for EBF 0-10 scores."""

from __future__ import annotations


def clamp_score(value: float) -> float:
    """Clamp any numeric score into the EBF 0-10 range."""
    return round(max(0.0, min(10.0, float(value))), 1)


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
