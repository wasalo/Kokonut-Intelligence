"""Shared constants, loop definitions, and configuration for systems thinking."""

from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Meadows' 12 Leverage Points (least to most effective)
# ---------------------------------------------------------------------------

LEVERAGE_POINTS: List[Dict[str, Any]] = [
    {
        "point": 12,
        "name": "Constants, Parameters, Numbers",
        "description": "Adjusting numbers, budgets, subsidies, or other parameters within existing structures",
        "farm_examples": ["alert_threshold", "sampling_interval", "budget_allocation"],
    },
    {
        "point": 11,
        "name": "Buffers and Stabilizing Stocks",
        "description": "Modifying reserves, inventories, or other stabilizing stocks relative to their flows",
        "farm_examples": ["soil_carbon_reserve", "water_reserve", "seed_stock", "cash_reserves"],
    },
    {
        "point": 10,
        "name": "Structure of Material Stocks and Flows",
        "description": "The physical layout or network through which resources move",
        "farm_examples": ["irrigation_network", "compost_system", "nutrient_cycling"],
    },
    {
        "point": 9,
        "name": "Lengths of Delays",
        "description": "The lengths of delays relative to the rate of system change",
        "farm_examples": ["intervention_to_effect", "certification_timeline", "soil_recovery_time"],
    },
    {
        "point": 8,
        "name": "Strength of Negative Feedback Loops",
        "description": "The strength of negative feedback loops relative to the impacts they correct",
        "farm_examples": ["anomaly_detection_sensitivity", "market_price_adjustment"],
    },
    {
        "point": 7,
        "name": "Positive Feedback Loops",
        "description": "The gain around reinforcing feedback loops",
        "farm_examples": ["degradation_escalation", "investment_returns", "knowledge_compounding"],
    },
    {
        "point": 6,
        "name": "Information Flows",
        "description": "Who has access to what information and when",
        "farm_examples": ["sensor_data_access", "market_price_transparency", "governance_information"],
    },
    {
        "point": 5,
        "name": "Rules of the System",
        "description": "Incentives, punishments, and constraints that govern behavior",
        "farm_examples": ["certification_standards", "governance_policies", "contract_terms"],
    },
    {
        "point": 4,
        "name": "Self-Organization",
        "description": "The power to add, change, or evolve system structure",
        "farm_examples": ["adaptive_sampling", "feature_flags", "driver_plugins"],
    },
    {
        "point": 3,
        "name": "Goals of the System",
        "description": "The purpose or function of the system",
        "farm_examples": ["regenerative_outcomes", "financial_sustainability", "community_wellbeing"],
    },
    {
        "point": 2,
        "name": "Paradigm or Mindset",
        "description": "The mindset out of which the system arises",
        "farm_examples": ["regenerative_vs_industrial", "short_term_vs_long_term"],
    },
    {
        "point": 1,
        "name": "Power to Transcend Paradigms",
        "description": "The ability to hold any single worldview lightly",
        "farm_examples": ["multiple_analytical_frameworks", "adaptive_governance"],
    },
]

# ---------------------------------------------------------------------------
# System Archetypes (Senge / Meadows)
# ---------------------------------------------------------------------------

ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "fixes_that_fail": {
        "name": "Fixes That Fail",
        "description": "A fix that seems to work short-term but has unintended consequences that worsen long-term",
        "structure": {
            "symptom": "initially_improves",
            "side_effect": "worsens_over_time",
            "fix": "applied_to_symptom",
        },
        "detection_signals": [
            "intervention followed by temporary improvement then decline",
            "increasing dependence on the same intervention",
            "declining effectiveness of repeated interventions",
        ],
    },
    "shifting_the_burden": {
        "name": "Shifting the Burden",
        "description": "An symptomatic solution is used to address a problem, reducing the incentive to find a fundamental solution",
        "structure": {
            "problem": "fundamental_issue",
            "symptom_fix": "easier_short_term",
            "fundamental_fix": "harder_long_term",
        },
        "detection_signals": [
            "increasing use of quick fixes",
            "decreasing investment in fundamental solutions",
            "erosion of capability to address root causes",
        ],
    },
    "erosion_of_goals": {
        "name": "Erosion of Goals",
        "description": "When performance falls below a goal, the goal is lowered rather than addressing the gap",
        "structure": {
            "actual_performance": "below_goal",
            "response": "lower_the_goal",
        },
        "detection_signals": [
            "declining standards over time",
            "acceptance of lower performance as normal",
            "goals adjusted downward after shortfalls",
        ],
    },
    "escalation": {
        "name": "Escalation",
        "description": "Two parties each see the other's actions as a threat and respond in ways that worsen the situation",
        "structure": {
            "party_a": "action_threatens_b",
            "party_b": "retaliation_threatens_a",
        },
        "detection_signals": [
            "increasing competition for shared resources",
            "arms-race dynamics in pricing or inputs",
            "deteriorating relationships between actors",
        ],
    },
    "success_to_the_successful": {
        "name": "Success to the Successful",
        "description": "The successful get more resources, which helps them succeed more, while others fall behind",
        "structure": {
            "winner": "receives_more_resources",
            "loser": "receives_fewer_resources",
        },
        "detection_signals": [
            "concentration of resources in few actors",
            "growing inequality in outcomes",
            "reduced diversity in the system",
        ],
    },
    "tragedy_of_the_commons": {
        "name": "Tragedy of the Commons",
        "description": "Individual actors deplete a shared resource acting in their own self-interest",
        "structure": {
            "shared_resource": "limited_capacity",
            "individual_use": "benefit_private",
            "individual_use": "cost_shared",
        },
        "detection_signals": [
            "declining shared resource levels",
            "increasing individual extraction rates",
            "degradation of shared infrastructure",
        ],
    },
}

# ---------------------------------------------------------------------------
# Predefined Causal Loops for Farm Systems
# ---------------------------------------------------------------------------

FARM_CAUSAL_LOOPS: List[Dict[str, Any]] = [
    {
        "loop_name": "soil_carbon_reinforcing",
        "loop_type": "reinforcing",
        "domain": "ecological",
        "description": "More soil carbon → better water retention → healthier plants → more residue → more soil carbon",
        "links": [
            {"source": "organic_matter", "target": "soil_carbon", "polarity": "+", "delay_hours": 8760},
            {"source": "soil_carbon", "target": "water_retention", "polarity": "+", "delay_hours": 720},
            {"source": "water_retention", "target": "plant_health", "polarity": "+", "delay_hours": 168},
            {"source": "plant_health", "target": "residue_return", "polarity": "+", "delay_hours": 2160},
            {"source": "residue_return", "target": "organic_matter", "polarity": "+", "delay_hours": 4320},
        ],
    },
    {
        "loop_name": "tillage_dependence_trap",
        "loop_type": "balancing",
        "domain": "ecological",
        "archetype": "fixes_that_fail",
        "description": "Tillage breaks compaction short-term but degrades soil structure long-term, creating more compaction",
        "links": [
            {"source": "soil_compaction", "target": "tillage_frequency", "polarity": "+", "delay_hours": 0},
            {"source": "tillage_frequency", "target": "soil_structure", "polarity": "-", "delay_hours": 4320},
            {"source": "soil_structure", "target": "soil_compaction", "polarity": "-", "delay_hours": 8760},
        ],
    },
    {
        "loop_name": "fertilizer_dependency",
        "loop_type": "balancing",
        "domain": "ecological",
        "archetype": "shifting_the_burden",
        "description": "Chemical fertilizer masks declining soil fertility, reducing incentive to build organic matter",
        "links": [
            {"source": "declining_fertility", "target": "fertilizer_use", "polarity": "+", "delay_hours": 0},
            {"source": "fertilizer_use", "target": "crop_yield", "polarity": "+", "delay_hours": 720},
            {"source": "crop_yield", "target": "soil_organic_matter", "polarity": "-", "delay_hours": 8760},
            {"source": "soil_organic_matter", "target": "declining_fertility", "polarity": "-", "delay_hours": 17520},
        ],
    },
    {
        "loop_name": "water_table_depletion",
        "loop_type": "reinforcing",
        "domain": "ecological",
        "archetype": "tragedy_of_the_commons",
        "description": "Multiple farms drawing from shared aquifer depletes water table for everyone",
        "links": [
            {"source": "individual_pumping", "target": "aquifer_level", "polarity": "-", "delay_hours": 0},
            {"source": "aquifer_level", "target": "water_access", "polarity": "-", "delay_hours": 0},
            {"source": "water_access", "target": "irrigation_dependence", "polarity": "-", "delay_hours": 0},
            {"source": "irrigation_dependence", "target": "individual_pumping", "polarity": "+", "delay_hours": 0},
        ],
    },
    {
        "loop_name": "knowledge_compounding",
        "loop_type": "reinforcing",
        "domain": "social",
        "description": "Training → better practices → better outcomes → more investment in training",
        "links": [
            {"source": "training_events", "target": "practice_quality", "polarity": "+", "delay_hours": 2160},
            {"source": "practice_quality", "target": "farm_outcomes", "polarity": "+", "delay_hours": 4320},
            {"source": "farm_outcomes", "target": "training_investment", "polarity": "+", "delay_hours": 0},
            {"source": "training_investment", "target": "training_events", "polarity": "+", "delay_hours": 0},
        ],
    },
    {
        "loop_name": "certification_value",
        "loop_type": "reinforcing",
        "domain": "financial",
        "description": "Certification → premium prices → reinvestment → maintaining certification",
        "links": [
            {"source": "certification_status", "target": "price_premium", "polarity": "+", "delay_hours": 0},
            {"source": "price_premium", "target": "revenue", "polarity": "+", "delay_hours": 0},
            {"source": "revenue", "target": "certification_investment", "polarity": "+", "delay_hours": 0},
            {"source": "certification_investment", "target": "certification_status", "polarity": "+", "delay_hours": 8760},
        ],
    },
    {
        "loop_name": "market_price_volatility",
        "loop_type": "reinforcing",
        "domain": "financial",
        "description": "High prices → more planting → oversupply → price crash → less planting → shortage → high prices",
        "links": [
            {"source": "market_price", "target": "planting_area", "polarity": "+", "delay_hours": 0},
            {"source": "planting_area", "target": "supply", "polarity": "+", "delay_hours": 4320},
            {"source": "supply", "target": "market_price", "polarity": "-", "delay_hours": 0},
        ],
    },
    {
        "loop_name": "biodiversity_resilience",
        "loop_type": "reinforcing",
        "domain": "ecological",
        "description": "More biodiversity → more pest predators → less pesticide → more biodiversity",
        "links": [
            {"source": "biodiversity", "target": "pest_predators", "polarity": "+", "delay_hours": 4320},
            {"source": "pest_predators", "target": "pesticide_need", "polarity": "-", "delay_hours": 2160},
            {"source": "pesticide_need", "target": "biodiversity", "polarity": "-", "delay_hours": 8760},
        ],
    },
]

# ---------------------------------------------------------------------------
# Time Delay Mappings
# ---------------------------------------------------------------------------

DEFAULT_TIME_DELAYS: List[Dict[str, Any]] = [
    {"action_type": "cover_crop_planting", "effect_type": "soil_carbon_increase", "expected_delay_hours": 17520, "min_delay_hours": 8760, "max_delay_hours": 43800, "domain": "ecological"},
    {"action_type": "organic_certification", "effect_type": "price_premium", "expected_delay_hours": 26280, "min_delay_hours": 17520, "max_delay_hours": 35040, "domain": "financial"},
    {"action_type": "training_event", "effect_type": "practice_adoption", "expected_delay_hours": 4320, "min_delay_hours": 2160, "max_delay_hours": 8760, "domain": "social"},
    {"action_type": "irrigation", "effect_type": "soil_moisture_increase", "expected_delay_hours": 6, "min_delay_hours": 1, "max_delay_hours": 24, "domain": "ecological"},
    {"action_type": "fertilizer_application", "effect_type": "yield_response", "expected_delay_hours": 1008, "min_delay_hours": 336, "max_delay_hours": 1344, "domain": "ecological"},
    {"action_type": "compost_application", "effect_type": "soil_structure_improvement", "expected_delay_hours": 4320, "min_delay_hours": 2160, "max_delay_hours": 8760, "domain": "ecological"},
    {"action_type": "pest_management_intervention", "effect_type": "pest_population_decline", "expected_delay_hours": 336, "min_delay_hours": 72, "max_delay_hours": 720, "domain": "ecological"},
    {"action_type": "water_conservation", "effect_type": "aquifer_recovery", "expected_delay_hours": 26280, "min_delay_hours": 8760, "max_delay_hours": 87600, "domain": "ecological"},
    {"action_type": "carbon_credit_issuance", "effect_type": "revenue_recognition", "expected_delay_hours": 720, "min_delay_hours": 168, "max_delay_hours": 2160, "domain": "financial"},
    {"action_type": "governance_reform", "effect_type": "community_trust_increase", "expected_delay_hours": 8760, "min_delay_hours": 4320, "max_delay_hours": 17520, "domain": "governance"},
    {"action_type": "diversification", "effect_type": "income_stability", "expected_delay_hours": 8760, "min_delay_hours": 4320, "max_delay_hours": 17520, "domain": "financial"},
    {"action_type": "soil_amendment", "effect_type": "ph_adjustment", "expected_delay_hours": 2160, "min_delay_hours": 720, "max_delay_hours": 4320, "domain": "ecological"},
    {"action_type": "agroforestry_planting", "effect_type": "microclimate_improvement", "expected_delay_hours": 17520, "min_delay_hours": 8760, "max_delay_hours": 43800, "domain": "ecological"},
    {"action_type": "community_engagement", "effect_type": "social_cohesion", "expected_delay_hours": 4320, "min_delay_hours": 2160, "max_delay_hours": 8760, "domain": "social"},
    {"action_type": "digital_infrastructure", "effect_type": "data_quality_improvement", "expected_delay_hours": 2160, "min_delay_hours": 720, "max_delay_hours": 4320, "domain": "governance"},
]

# ---------------------------------------------------------------------------
# Worldview Dimensions for Mental Models
# ---------------------------------------------------------------------------

WORLDVIEW_DIMENSIONS: List[Dict[str, Any]] = [
    {"dimension": "regenerative_vs_industrial", "label_low": "Industrial", "label_high": "Regenerative", "domain": "agricultural"},
    {"dimension": "short_term_vs_long_term", "label_low": "Short-term focused", "label_high": "Long-term focused", "domain": "temporal"},
    {"dimension": "individual_vs_collective", "label_low": "Individual benefit", "label_high": "Collective benefit", "domain": "social"},
    {"dimension": "risk_aversion_vs_taking", "label_low": "Risk averse", "label_high": "Risk tolerant", "domain": "financial"},
    {"dimension": "technology_adoption", "label_low": "Traditional methods", "label_high": "Technology forward", "domain": "operational"},
    {"dimension": "market_orientation", "label_low": "Subsistence focused", "label_high": "Market oriented", "domain": "economic"},
    {"dimension": "data_trust", "label_low": "Intuition based", "label_high": "Data driven", "domain": "decision"},
    {"dimension": "governance_preference", "label_low": "Centralized", "label_high": "Distributed", "domain": "governance"},
]
