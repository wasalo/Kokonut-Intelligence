"""Shared source-manifest collection for safe synthesis views."""

from __future__ import annotations

import re
from typing import Any

import pytest

from services.agents.bio_factory_agent import BioFactorySynthesisAgent
from services.agents.capital_efficiency_agent import CapitalEfficiencySynthesisAgent
from services.agents.commons_agent import CommonsSynthesisAgent
from services.agents.feedback_agent import FeedbackSynthesisAgent
from services.agents.gnh_agent import GnhSynthesisAgent
from services.agents.kokonut_commons_agent import KokonutCommonsSynthesisAgent
from services.agents.open_source_capitalist_agent import OpenSourceCapitalistSynthesisAgent
from services.agents.regenerator_agent import RegeneratorSynthesisAgent
from services.agents.resilience_agent import ResilienceSynthesisAgent
from services.agents.wellbeing_agent import WellbeingSynthesisAgent
from services.agents.worker_draft import SYNTHESIS_SUMMARY_TYPES, _validate_source_references

AGENTS = [
    CapitalEfficiencySynthesisAgent,
    BioFactorySynthesisAgent,
    RegeneratorSynthesisAgent,
    CommonsSynthesisAgent,
    GnhSynthesisAgent,
    ResilienceSynthesisAgent,
    OpenSourceCapitalistSynthesisAgent,
    WellbeingSynthesisAgent,
    FeedbackSynthesisAgent,
    KokonutCommonsSynthesisAgent,
]
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


def test_worker_summary_type_registry_covers_all_shared_synthesis_agents() -> None:
    assert {agent.summary_type for agent in AGENTS} == SYNTHESIS_SUMMARY_TYPES


class _Cursor:
    def __init__(self, source_tables: list[str]) -> None:
        self.source_tables = source_tables
        self.query = ""
        self.params: tuple[Any, ...] = ()

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[dict[str, Any]]:
        return [
            {
                "source_table": table,
                "row_count": 51,
                "record_ids": [
                    f"e0000000-0000-4000-8000-{index:012d}"
                    for index in range(1, 51)
                ],
            }
            for table in self.source_tables
        ]

    def close(self) -> None:
        pass


class _Connection:
    def __init__(self, source_tables: list[str]) -> None:
        self.cursor_value = _Cursor(source_tables)

    def cursor(self, cursor_factory: Any = None) -> _Cursor:
        return self.cursor_value


@pytest.mark.parametrize("agent_class", AGENTS)
def test_location_source_reference_collector_uses_bounded_public_views(agent_class: Any) -> None:
    connection = _Connection(list(agent_class.source_reference_views))
    agent = agent_class()

    references = agent.collect_source_references(connection, LOCATION_ID)

    assert set(references) == set(agent.source_reference_views)
    assert all(
        re.search(
            rf"\bFROM\s+(?:public\.)?{re.escape(view)}\b",
            connection.cursor_value.query,
            re.IGNORECASE,
        )
        for view in agent.source_reference_views.values()
    )
    assert connection.cursor_value.query.count("WHERE location_id = %s") == len(agent.source_reference_views)
    assert connection.cursor_value.params == (LOCATION_ID,) * len(agent.source_reference_views)
    assert all(reference["row_count"] == 51 for reference in references.values())
    assert all(len(reference["record_ids"]) == 50 for reference in references.values())
    assert all(reference["truncated"] for reference in references.values())


@pytest.mark.parametrize("agent_class", AGENTS)
def test_worker_adapter_accepts_each_agent_manifest_source(agent_class: Any) -> None:
    source_tables = list(agent_class.source_reference_views)
    references = {
        table: {
            "record_ids": [f"e0000000-0000-4000-8000-{index:012d}"],
            "row_count": 1,
            "truncated": False,
        }
        for index, table in enumerate(source_tables, start=501)
    }

    validated, serialized = _validate_source_references(references, source_tables)

    assert validated == references
    assert serialized


def test_global_catalogue_sources_are_not_registered_as_location_manifests() -> None:
    assert "bio_regional_input_availability" not in BioFactorySynthesisAgent.source_reference_views
    assert "network_scaling_target" not in OpenSourceCapitalistSynthesisAgent.source_reference_views
    assert "open_source_impact_artifact" not in OpenSourceCapitalistSynthesisAgent.source_reference_views
    assert "green_paper_publication_review" not in ResilienceSynthesisAgent.source_reference_views
    assert "federation_protocol" not in KokonutCommonsSynthesisAgent.source_reference_views
    assert "participatory_signal_experiment" not in KokonutCommonsSynthesisAgent.source_reference_views


def test_feedback_sources_use_only_consent_approved_published_views() -> None:
    assert WellbeingSynthesisAgent.source_reference_views["stakeholder_feedback"] == (
        "v_public_stakeholder_feedback_summary"
    )
    assert FeedbackSynthesisAgent.source_reference_views == {
        "stakeholder_feedback": "v_public_stakeholder_feedback_summary"
    }
