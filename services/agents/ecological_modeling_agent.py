"""Ecological modeling agent: synthesizes ecological interaction, energy flow, pest, soil input, and resource data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.agents.base import SynthesisAgent, require_synthesis_location_id
from services.analytics.ecological_modeling import (
    compute_energy_flow_efficiency,
    compute_population_stability,
    compute_trophic_balance,
    trophic_pyramid_summary,
)
from services.analytics.ecological_modeling_v2 import (
    compute_biocontrol_effectiveness,
    compute_conservation_status_summary,
    compute_pest_trends,
    compute_resource_efficiency,
    compute_soil_input_retention,
)
from services.analytics.livestock_feed import (
    compute_feed_conversion_ratio,
    compute_feed_intake_summary,
)
from services.analytics.reward_calibration import (
    compute_reward_calibration,
    compute_reward_calibration_model,
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
    location_id = require_synthesis_location_id(location_id)
    # Keep the legacy analytics SQL stable while resolving its relation names
    # only against signed, location-filtered worker projections.
    with conn.cursor() as cursor:
        cursor.execute("SET LOCAL search_path = kokonut_agent_source, pg_catalog")

    trophic = compute_trophic_balance(conn, location_id)
    energy = compute_energy_flow_efficiency(conn, location_id)
    population = compute_population_stability(conn, location_id)
    pyramid = trophic_pyramid_summary(conn, location_id)
    soil_inputs = compute_soil_input_retention(conn, location_id)
    pest_trends = compute_pest_trends(conn, location_id)
    biocontrol = compute_biocontrol_effectiveness(conn, location_id)
    resources = compute_resource_efficiency(conn, location_id)
    conservation = compute_conservation_status_summary(conn, location_id)
    feed_intake = compute_feed_intake_summary(conn, location_id)
    feed_conversion = compute_feed_conversion_ratio(conn, location_id)
    reward_cal = compute_reward_calibration(conn, location_id)
    reward_model = compute_reward_calibration_model(conn, location_id)

    return {
        "location_id": location_id,
        "synthesized_at": datetime.now(timezone.utc).isoformat(),
        "trophic_balance": trophic,
        "energy_flow": energy,
        "population_stability": population,
        "pyramid": pyramid,
        "soil_inputs": soil_inputs,
        "pest_trends": pest_trends,
        "biocontrol": biocontrol,
        "resource_efficiency": resources,
        "conservation_status": conservation,
        "livestock_feed": feed_intake,
        "feed_conversion": feed_conversion,
        "reward_calibration": reward_cal,
        "reward_model": reward_model,
        "safety_note": SAFETY_NOTE,
        "limitations": [
            "Ecological modeling outputs are advisory, not deterministic predictions.",
            "Interaction strength values are observational estimates.",
            "Population dynamics depend on survey method accuracy.",
            "Energy flow measurements use estimation methods.",
            "Pest outbreak probability is a model estimate, not a certainty.",
            "Biocontrol effectiveness depends on environmental conditions.",
            "Resource consumption may include estimated values.",
            "Soil input retention rates vary with soil type and climate.",
            "Agent synthesis is a draft; not verified or published without human review.",
        ],
    }


class EcologicalModelingSynthesisAgent(SynthesisAgent):
    """Run ecological analytics through signed, exact-location projections."""

    task_key = "ecological_modeling_synthesis"
    summary_type = "ecological_modeling"
    read_collection = "ecological_interaction"
    model_version = "ecological-modeling-agent-v1"
    source_tables = [
        "ecological_interaction", "energy_flow_measurement",
        "population_dynamics_record", "soil_input_application",
        "pest_observation", "biocontrol_release", "resource_consumption",
        "harvest_event", "location", "species_observation", "livestock_group",
        "feed_intake_record", "token_reward_distribution", "reward_calibration_model",
    ]
    # Row-level provenance records only IDs from reviewed public projections.
    # The farm row itself is the already-bound summary subject, so it remains
    # a source-table hint rather than a redundant manifest entry.
    source_reference_views = {
        "ecological_interaction": "v_public_ecological_interaction_summary",
        "energy_flow_measurement": "v_public_energy_flow_summary",
        "population_dynamics_record": "v_public_population_dynamics_summary",
        "soil_input_application": "v_public_soil_input_retention",
        "pest_observation": "v_public_pest_trends",
        "biocontrol_release": "v_public_biocontrol_effectiveness",
        "resource_consumption": "v_public_resource_efficiency",
        "species_observation": "v_public_ecological_species_conservation",
        "harvest_event": "v_public_ecological_harvest_event_reference",
        "livestock_group": "v_public_ecological_livestock_group_reference",
        "feed_intake_record": "v_public_ecological_feed_intake_reference",
        "token_reward_distribution": "v_public_token_reward_distribution",
        "reward_calibration_model": "v_public_reward_calibration",
    }
    source_reference_exclusions = {
        "location": "The location is the already-bound synthesis subject, not a separate source record."
    }

    def synthesize(self, conn, location_id=None):
        return synthesize_ecological_modeling(conn, location_id)


agent = EcologicalModelingSynthesisAgent()
