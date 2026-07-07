"""Ecological modeling agent: synthesizes ecological interaction, energy flow, and population dynamics data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from services.analytics.ecological_modeling import (
    compute_energy_flow_efficiency,
    compute_population_stability,
    compute_trophic_balance,
    trophic_pyramid_summary,
)
from services.common.logging import get_logger

logger = get_logger(__name__)

SAFETY_NOTE = (
    "Ecological modeling outputs are advisory estimates derived from observational data. "
    "They are not deterministic predictions and should not be used as sole basis for management decisions. "
    "Ground-truth verification is required before operational use."
)


def synthesize_ecological_modeling(conn, location_id: str) -> dict[str, Any]:
    """Synthesize ecological modeling data for a location into a public-safe summary."""
    trophic = compute_trophic_balance(conn, location_id)
    energy = compute_energy_flow_efficiency(conn, location_id)
    population = compute_population_stability(conn, location_id)
    pyramid = trophic_pyramid_summary(conn, location_id)

    return {
        "location_id": location_id,
        "synthesized_at": datetime.now(timezone.utc).isoformat(),
        "trophic_balance": trophic,
        "energy_flow": energy,
        "population_stability": population,
        "pyramid": pyramid,
        "safety_note": SAFETY_NOTE,
        "limitations": [
            "Ecological modeling outputs are advisory, not deterministic predictions.",
            "Interaction strength values are observational estimates.",
            "Population dynamics depend on survey method accuracy.",
            "Energy flow measurements use estimation methods.",
            "Agent synthesis is a draft; not verified or published without human review.",
        ],
    }
