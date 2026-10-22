"""Shared source-manifest collection for safe synthesis views."""

from __future__ import annotations

import re
from pathlib import Path
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
SYNTHESIS_RELATION = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-zA-Z_][\w$]*)", re.IGNORECASE
)


def test_worker_summary_type_registry_covers_all_shared_synthesis_agents() -> None:
    assert {agent.summary_type for agent in AGENTS} == SYNTHESIS_SUMMARY_TYPES


class _QueryRecordingCursor:
    def __init__(self) -> None:
        self.queries: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> None:
        self.queries.append((query, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return []

    def close(self) -> None:
        pass


class _QueryRecordingConnection:
    def __init__(self) -> None:
        self.cursor_value = _QueryRecordingCursor()

    def cursor(self, cursor_factory: Any = None) -> _QueryRecordingCursor:
        return self.cursor_value


@pytest.mark.parametrize("agent_class", AGENTS)
def test_synthesis_queries_read_only_registered_public_views(agent_class: Any) -> None:
    connection = _QueryRecordingConnection()

    agent_class().synthesize(connection, LOCATION_ID)

    view_sources = {
        view: source for source, view in agent_class.source_reference_views.items()
    }
    relations = {
        relation
        for query, _ in connection.cursor_value.queries
        for relation in SYNTHESIS_RELATION.findall(query)
    }
    approved_views = set(agent_class.source_reference_views.values())

    assert relations
    assert all(relation.startswith("v_public_") for relation in relations)
    assert relations <= approved_views

    for query, params in connection.cursor_value.queries:
        assert re.match(r"\s*SELECT\b", query, re.IGNORECASE)
        for relation in SYNTHESIS_RELATION.findall(query):
            source = view_sources[relation]
            scope = agent_class.source_reference_scopes.get(source, "location")
            location_bound = re.search(r"\blocation_id\s*=\s*%s", query, re.IGNORECASE)
            includes_unassigned = re.search(
                r"\blocation_id\s+IS\s+NULL", query, re.IGNORECASE
            )

            if scope == "network":
                assert params is None
                assert location_bound is None
                assert includes_unassigned is None
            else:
                assert params == (LOCATION_ID,)
                assert location_bound is not None
                assert (includes_unassigned is not None) == (
                    scope == "location_or_network"
                )


def test_registered_synthesis_views_match_migration_select_allowlist() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/541_agent_synthesis_source_reader.sql"
    ).read_text()
    grant = migration.split("GRANT SELECT ON TABLE", 1)[1].split(
        "TO kokonut_agent_summary_source_reader;", 1
    )[0]
    granted_views = set(re.findall(r"public\.([a-z][a-z0-9_]*)", grant))
    registered_views = {
        view for agent_class in AGENTS for view in agent_class.source_reference_views.values()
    }

    assert len(registered_views) == 40
    assert granted_views == registered_views


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
    expected_bound = sum(
        agent_class.source_reference_scopes.get(table, "location") != "network"
        for table in agent_class.source_reference_views
    )
    assert connection.cursor_value.query.count("WHERE location_id = %s") == expected_bound
    assert connection.cursor_value.params == (LOCATION_ID,) * expected_bound
    assert all(reference["row_count"] == 51 for reference in references.values())
    assert all(len(reference["record_ids"]) == 50 for reference in references.values())
    assert all(reference["truncated"] for reference in references.values())
    assert all(
        reference.get("scope", "location")
        == agent_class.source_reference_scopes.get(table, "location")
        for table, reference in references.items()
    )


@pytest.mark.parametrize("agent_class", AGENTS)
def test_worker_adapter_accepts_each_agent_manifest_source(agent_class: Any) -> None:
    source_tables = list(agent_class.source_reference_views)
    references = {
        table: {
            "record_ids": [f"e0000000-0000-4000-8000-{index:012d}"],
            "row_count": 1,
            "truncated": False,
            **(
                {"scope": agent_class.source_reference_scopes[table]}
                if agent_class.source_reference_scopes.get(table, "location") != "location"
                else {}
            ),
        }
        for index, table in enumerate(source_tables, start=501)
    }

    validated, serialized = _validate_source_references(references, source_tables)

    assert validated == references
    assert serialized


def test_global_and_shared_sources_have_explicit_scopes() -> None:
    assert BioFactorySynthesisAgent.source_reference_scopes["bio_regional_input_availability"] == "network"
    assert OpenSourceCapitalistSynthesisAgent.source_reference_scopes["network_scaling_target"] == "network"
    assert OpenSourceCapitalistSynthesisAgent.source_reference_scopes["open_source_impact_artifact"] == "network"
    assert ResilienceSynthesisAgent.source_reference_scopes["green_paper_publication_review"] == "network"
    assert KokonutCommonsSynthesisAgent.source_reference_scopes["federation_protocol"] == "network"
    assert KokonutCommonsSynthesisAgent.source_reference_scopes["participatory_signal_experiment"] == "network"
    assert OpenSourceCapitalistSynthesisAgent.source_reference_scopes["farm_launch_unit_economics"] == "location_or_network"
    assert KokonutCommonsSynthesisAgent.source_reference_scopes["anti_capture_governance_policy"] == "location_or_network"


def test_feedback_sources_use_only_consent_approved_published_views() -> None:
    assert WellbeingSynthesisAgent.source_reference_views["stakeholder_feedback"] == (
        "v_public_stakeholder_feedback_summary"
    )
    assert FeedbackSynthesisAgent.source_reference_views == {
        "stakeholder_feedback": "v_public_stakeholder_feedback_summary"
    }


def test_instance_override_cannot_replace_registered_source_reference_query() -> None:
    agent = CapitalEfficiencySynthesisAgent()
    registered_query = CapitalEfficiencySynthesisAgent.source_reference_query
    agent.source_reference_query = "SELECT 'harvest_event' AS source_table, id FROM harvest_event"
    connection = _Connection(list(CapitalEfficiencySynthesisAgent.source_reference_views))

    references = agent.collect_source_references(connection, LOCATION_ID)

    assert connection.cursor_value.query == registered_query
    assert "FROM harvest_event" not in connection.cursor_value.query
    assert set(references) == set(CapitalEfficiencySynthesisAgent.source_reference_views)
