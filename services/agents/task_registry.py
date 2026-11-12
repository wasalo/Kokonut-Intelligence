"""Source-controlled registry for operator-requested synthesis tasks."""

from __future__ import annotations

from types import MappingProxyType

TASK_SUMMARY_TYPES = MappingProxyType({
    "ai_summary_synthesis": frozenset({"operations", "financial", "environmental", "combined"}),
    "organic_readiness_synthesis": frozenset({"organic_readiness"}),
    "ecological_modeling_synthesis": frozenset({"ecological_modeling"}),
    "holistic_wellbeing_synthesis": frozenset({"holistic_wellbeing"}),
    "feedback_synthesis": frozenset({"stakeholder_feedback"}),
    "commons_liberation_synthesis": frozenset({"commons_liberation"}),
    "gnh_alignment_synthesis": frozenset({"gnh_alignment"}),
    "regenerator_synthesis": frozenset({"regenerative_outcomes"}),
    "capital_efficiency_synthesis": frozenset({"capital_efficiency"}),
    "financial_resilience_synthesis": frozenset({"financial_resilience"}),
    "bio_factory_synthesis": frozenset({"bio_factory"}),
    "open_source_capitalist_synthesis": frozenset({"open_source_capitalist"}),
    "kokonut_commons_synthesis": frozenset({"kokonut_commons"}),
})


TASK_WORKER_KEYS = MappingProxyType({
    "ai_summary_synthesis": "agent_summary_deterministic_source",
    "organic_readiness_synthesis": "agent_organic_readiness_source",
    "ecological_modeling_synthesis": "agent_ecological_modeling_source",
    "holistic_wellbeing_synthesis": "agent_holistic_wellbeing_source",
    "feedback_synthesis": "agent_feedback_source",
    "commons_liberation_synthesis": "agent_commons_liberation_source",
    "gnh_alignment_synthesis": "agent_gnh_alignment_source",
    "regenerator_synthesis": "agent_regenerator_source",
    "capital_efficiency_synthesis": "agent_capital_efficiency_source",
    "financial_resilience_synthesis": "agent_financial_resilience_source",
    "bio_factory_synthesis": "agent_bio_factory_source",
    "open_source_capitalist_synthesis": "agent_open_source_capitalist_source",
    "kokonut_commons_synthesis": "agent_kokonut_commons_source",
})

if TASK_SUMMARY_TYPES.keys() != TASK_WORKER_KEYS.keys():
    raise RuntimeError("Every registered synthesis task must have exactly one worker identity")
