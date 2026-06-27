"""Lightweight EBF pillar score calculators.

These helpers normalize already-governed metric values. They do not fetch raw
farm evidence or publish scorecards; those remain review/governance steps.
"""

from __future__ import annotations

from .normalization import normalize_linear, normalize_percentage


def compute_air_quality_score(kg_co2e_per_acre: float) -> float:
    return normalize_linear(kg_co2e_per_acre, 0, 5000)


def compute_water_management_score(runoff_reduction_pct: float) -> float:
    return normalize_percentage(runoff_reduction_pct)


def compute_soil_health_score(soc_change_pct: float) -> float:
    return normalize_linear(soc_change_pct, -2, 8)


def compute_biodiversity_score(species_richness_index: float) -> float:
    return normalize_linear(species_richness_index, 0, 100)


def compute_carbon_sequestration_score(total_farm_co2e: float, farm_area_ha: float) -> float:
    if farm_area_ha <= 0:
        raise ValueError("farm_area_ha must be positive")
    return normalize_linear(total_farm_co2e / farm_area_ha, 0, 20)


def compute_equity_community_score(local_worker_pct: float, training_hours_per_worker: float) -> float:
    worker_score = normalize_percentage(local_worker_pct)
    training_score = normalize_linear(training_hours_per_worker, 0, 40)
    return round((worker_score + training_score) / 2, 1)


def compute_implementation_quality_score(smart_kpi_completion_pct: float) -> float:
    return normalize_percentage(smart_kpi_completion_pct)
