"""Rubric band assignment for EBF 0-10 scores."""

from __future__ import annotations

from dataclasses import dataclass

from .normalization import clamp_score


@dataclass(frozen=True)
class RubricBand:
    score_value: int
    band_min: float
    band_max: float
    band_label: str


def band_label_for_score(score: float) -> str:
    """Return the default EBF rubric label for a normalized score."""
    value = int(clamp_score(score))
    if value <= 1:
        return "insufficient"
    if value <= 3:
        return "emerging"
    if value <= 5:
        return "developing"
    if value <= 7:
        return "strong"
    return "leading"


def assign_default_band(score: float) -> RubricBand:
    """Assign one of the 10 default integer rubric bands."""
    value = int(clamp_score(score))
    return RubricBand(
        score_value=value,
        band_min=float(value),
        band_max=10.0 if value == 9 else float(value + 1),
        band_label=band_label_for_score(value),
    )
