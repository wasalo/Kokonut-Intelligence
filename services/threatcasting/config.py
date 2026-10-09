"""Configuration for Threatcasting service: GNH dimensions, desirability weights,
threat type defaults, and cross-impact parameters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# GNH (Gross National Happiness) Dimensions
# Used for desirability assessment of threat narratives
# ---------------------------------------------------------------------------
GNH_DIMENSIONS: List[Dict[str, Any]] = [
    {"name": "psychological_wellbeing", "weight": 0.15, "description": "Life satisfaction, positive emotions, mental health"},
    {"name": "community_vitality", "weight": 0.12, "description": "Social support, community engagement, relationships"},
    {"name": "culture", "weight": 0.10, "description": "Cultural preservation, traditional knowledge, identity"},
    {"name": "time_use", "weight": 0.08, "description": "Work-life balance, leisure, time autonomy"},
    {"name": "education", "weight": 0.10, "description": "Access to learning, knowledge sharing, skill development"},
    {"name": "health", "weight": 0.12, "description": "Physical health, healthcare access, vitality"},
    {"name": "good_governance", "weight": 0.10, "description": "Transparency, participation, accountability"},
    {"name": "ecological_diversity", "weight": 0.13, "description": "Biodiversity, ecosystem health, natural beauty"},
    {"name": "living_standards", "weight": 0.10, "description": "Income, housing, basic needs, material security"},
]


# ---------------------------------------------------------------------------
# Eight Forms of Capital (alternative framework)
# ---------------------------------------------------------------------------
EIGHT_FORMS_OF_CAPITAL: List[Dict[str, Any]] = [
    {"name": "financial", "weight": 0.12, "description": "Money, investments, cash flow, financial reserves"},
    {"name": "social", "weight": 0.12, "description": "Relationships, networks, trust, social cohesion"},
    {"name": "living", "weight": 0.15, "description": "Plants, animals, soil, water, ecosystems"},
    {"name": "cultural", "weight": 0.10, "description": "Traditions, language, stories, collective wisdom"},
    {"name": "intellectual", "weight": 0.10, "description": "Knowledge, education, skills, information"},
    {"name": "emotional", "weight": 0.10, "description": "Mental health, resilience, capacity for feeling"},
    {"name": "spiritual", "weight": 0.08, "description": "Values, purpose, connection, meaning"},
    {"name": "built", "weight": 0.13, "description": "Infrastructure, tools, technology, buildings"},
]


# ---------------------------------------------------------------------------
# SDG Alignment (Sustainable Development Goals)
# ---------------------------------------------------------------------------
SDG_ALIGNMENT: List[Dict[str, Any]] = [
    {"name": "no_poverty", "sdg": 1, "weight": 0.08},
    {"name": "zero_hunger", "sdg": 2, "weight": 0.12},
    {"name": "good_health", "sdg": 3, "weight": 0.10},
    {"name": "quality_education", "sdg": 4, "weight": 0.08},
    {"name": "gender_equality", "sdg": 5, "weight": 0.06},
    {"name": "clean_water", "sdg": 6, "weight": 0.10},
    {"name": "affordable_energy", "sdg": 7, "weight": 0.06},
    {"name": "decent_work", "sdg": 8, "weight": 0.08},
    {"name": "industry_innovation", "sdg": 9, "weight": 0.04},
    {"name": "reduced_inequalities", "sdg": 10, "weight": 0.06},
    {"name": "sustainable_cities", "sdg": 11, "weight": 0.04},
    {"name": "responsible_consumption", "sdg": 12, "weight": 0.06},
    {"name": "climate_action", "sdg": 13, "weight": 0.12},
    {"name": "life_below_water", "sdg": 14, "weight": 0.02},
    {"name": "life_on_land", "sdg": 15, "weight": 0.04},
]


# ---------------------------------------------------------------------------
# Threat Type Defaults
# ---------------------------------------------------------------------------
THREAT_TYPE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "climate": {
        "velocity": "moderate",
        "reversibility": "partially",
        "typical_horizon_years": 10,
        "severity_weights": {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0},
    },
    "policy": {
        "velocity": "fast",
        "reversibility": "reversible",
        "typical_horizon_years": 5,
        "severity_weights": {"low": 0.3, "medium": 0.6, "high": 0.85, "critical": 1.0},
    },
    "market": {
        "velocity": "rapid",
        "reversibility": "reversible",
        "typical_horizon_years": 3,
        "severity_weights": {"low": 0.25, "medium": 0.55, "high": 0.8, "critical": 1.0},
    },
    "technology": {
        "velocity": "fast",
        "reversibility": "partially",
        "typical_horizon_years": 5,
        "severity_weights": {"low": 0.15, "medium": 0.45, "high": 0.75, "critical": 1.0},
    },
    "ecological": {
        "velocity": "slow",
        "reversibility": "irreversible",
        "typical_horizon_years": 15,
        "severity_weights": {"low": 0.3, "medium": 0.6, "high": 0.9, "critical": 1.0},
    },
    "social": {
        "velocity": "moderate",
        "reversibility": "partially",
        "typical_horizon_years": 7,
        "severity_weights": {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0},
    },
    "health": {
        "velocity": "rapid",
        "reversibility": "partially",
        "typical_horizon_years": 3,
        "severity_weights": {"low": 0.35, "medium": 0.65, "high": 0.9, "critical": 1.0},
    },
    "security": {
        "velocity": "rapid",
        "reversibility": "irreversible",
        "typical_horizon_years": 5,
        "severity_weights": {"low": 0.4, "medium": 0.7, "high": 0.95, "critical": 1.0},
    },
}


# ---------------------------------------------------------------------------
# Cross-Impact Types
# ---------------------------------------------------------------------------
CROSS_IMPACT_TYPES: List[Dict[str, Any]] = [
    {"type": "amplifies", "description": "Source threat increases severity/probability of target", "default_magnitude": 0.5},
    {"type": "attenuates", "description": "Source threat reduces severity/probability of target", "default_magnitude": 0.3},
    {"type": "triggers", "description": "Source threat directly activates target threat", "default_magnitude": 0.8},
    {"type": "delays", "description": "Source threat slows onset of target threat", "default_magnitude": 0.4},
    {"type": "redirects", "description": "Source threat changes manifestation of target threat", "default_magnitude": 0.5},
    {"type": "enables", "description": "Source threat creates conditions for target threat", "default_magnitude": 0.6},
]


# ---------------------------------------------------------------------------
# Flag Status Thresholds
# ---------------------------------------------------------------------------
FLAG_STATUS_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "quantitative": {
        "critical_ratio": 0.9,
        "warning_ratio": 0.7,
        "elevated_ratio": 0.5,
    },
    "pattern": {
        "critical_count": 5,
        "warning_count": 3,
        "elevated_count": 1,
    },
}


# ---------------------------------------------------------------------------
# Velocity Multipliers
# Used to adjust threat probability over time
# ---------------------------------------------------------------------------
VELOCITY_MULTIPLIERS: Dict[str, float] = {
    "slow": 0.05,       # 5% increase per year
    "moderate": 0.10,   # 10% increase per year
    "fast": 0.20,       # 20% increase per year
    "rapid": 0.40,      # 40% increase per year
}


# ---------------------------------------------------------------------------
# Cascade Configuration
# ---------------------------------------------------------------------------
CASCADE_CONFIG = {
    "max_chain_length": 10,
    "min_probability_threshold": 0.01,
    "evaluation_window_days": 90,
    "early_warning_buffer_hours": 72,
}


# ---------------------------------------------------------------------------
# Horizon Configuration
# ---------------------------------------------------------------------------
HORIZON_DEFAULTS = {
    "review_frequency_months": 12,
    "default_horizons": [
        {"name": "Immediate", "years": 1, "focus": ["operational", "financial"]},
        {"name": "Short-term", "years": 3, "focus": ["strategic", "market"]},
        {"name": "Medium-term", "years": 5, "focus": ["climate", "policy", "ecological"]},
        {"name": "Long-term", "years": 10, "focus": ["systemic", "civilizational"]},
    ],
}


@dataclass
class ThreatcastingConfig:
    """Main configuration class for threatcasting service."""
    gnh_dimensions: List[Dict[str, Any]] = field(default_factory=lambda: GNH_DIMENSIONS)
    eight_forms: List[Dict[str, Any]] = field(default_factory=lambda: EIGHT_FORMS_OF_CAPITAL)
    sdg_alignment: List[Dict[str, Any]] = field(default_factory=lambda: SDG_ALIGNMENT)
    threat_defaults: Dict[str, Dict[str, Any]] = field(default_factory=lambda: THREAT_TYPE_DEFAULTS)
    cross_impact_types: List[Dict[str, Any]] = field(default_factory=lambda: CROSS_IMPACT_TYPES)
    velocity_multipliers: Dict[str, float] = field(default_factory=lambda: VELOCITY_MULTIPLIERS)
    cascade_config: Dict[str, Any] = field(default_factory=lambda: CASCADE_CONFIG)
    horizon_defaults: Dict[str, Any] = field(default_factory=lambda: HORIZON_DEFAULTS)
    flag_thresholds: Dict[str, Dict[str, float]] = field(default_factory=lambda: FLAG_STATUS_THRESHOLDS)
