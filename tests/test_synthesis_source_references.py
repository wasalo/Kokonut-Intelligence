"""Shared source-manifest collection for safe synthesis views."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from services.agents.bio_factory_agent import BioFactorySynthesisAgent
from services.agents.capital_efficiency_agent import CapitalEfficiencySynthesisAgent
from services.agents.commons_agent import CommonsSynthesisAgent
from services.agents.ecological_modeling_agent import EcologicalModelingSynthesisAgent
from services.agents.feedback_agent import FeedbackSynthesisAgent
from services.agents.gnh_agent import GnhSynthesisAgent
from services.agents.kokonut_commons_agent import KokonutCommonsSynthesisAgent
from services.agents.open_source_capitalist_agent import OpenSourceCapitalistSynthesisAgent
from services.agents.organic_readiness_agent import OrganicReadinessSynthesisAgent
from services.agents.regenerator_agent import RegeneratorSynthesisAgent
from services.agents.resilience_agent import ResilienceSynthesisAgent
from services.agents.tasks import get_task
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
    OrganicReadinessSynthesisAgent,
    EcologicalModelingSynthesisAgent,
]
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
SYNTHESIS_RELATION = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:(?:public|kokonut_agent_source)\.)?([a-zA-Z_][\w$]*)",
    re.IGNORECASE,
)


def test_worker_summary_type_registry_covers_all_shared_synthesis_agents() -> None:
    assert {agent.summary_type for agent in AGENTS} == SYNTHESIS_SUMMARY_TYPES
    assert all(
        get_task(agent.task_key)["inputs"]["location_id"]["required"]
        for agent in AGENTS
    )


def test_registered_agent_source_hints_are_only_the_reviewed_exceptions() -> None:
    omissions = {
        agent.task_key: set(agent.source_tables) - set(agent.source_reference_views)
        for agent in AGENTS
    }
    omissions = {task: tables for task, tables in omissions.items() if tables}

    assert omissions == {
        "organic_readiness_synthesis": {"organic_compliance_checklist"},
        "ecological_modeling_synthesis": {"location"},
    }

    organic_migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/549_signed_organic_readiness_synthesis_source.sql"
    ).read_text()
    checklist_view = re.search(
        r"CREATE OR REPLACE VIEW kokonut_agent_source\.organic_compliance_checklist.*?;",
        organic_migration,
        re.DOTALL,
    )
    assert checklist_view is not None
    assert "SELECT source_row.id, source_row.location_id" in checklist_view.group()
    assert not re.search(
        r"\b(?:inspector_name|findings|non_conformances|evidence_urls|notes)\b",
        checklist_view.group(),
    )


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
def test_synthesis_queries_read_only_registered_scoped_views(agent_class: Any) -> None:
    if agent_class in {OrganicReadinessSynthesisAgent, EcologicalModelingSynthesisAgent}:
        # Both agents reuse legacy analytics SQL through narrow transaction-
        # local aliases; their search-path contracts are exercised separately.
        return
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
    assert relations == approved_views

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


class _CursorForbiddenConnection:
    def cursor(self, cursor_factory: Any = None) -> None:
        raise AssertionError("missing location must fail before cursor access")


@pytest.mark.parametrize("agent_class", AGENTS)
def test_synthesis_rejects_missing_location_before_cursor_access(agent_class: Any) -> None:
    with pytest.raises(ValueError, match="requires an exact location_id"):
        agent_class().synthesize(_CursorForbiddenConnection(), None)


@pytest.mark.parametrize("agent_class", AGENTS)
def test_synthesis_rejects_malformed_location_before_cursor_access(
    agent_class: Any,
) -> None:
    with pytest.raises(ValueError, match="requires a valid location_id UUID"):
        agent_class().synthesize(_CursorForbiddenConnection(), "not-a-uuid")


@pytest.mark.parametrize("agent_class", AGENTS)
def test_agent_run_rejects_missing_location_before_database_access(
    agent_class: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_database_opens() -> None:
        raise AssertionError("locationless synthesis must not open the database")

    monkeypatch.setattr(
        "services.agents.base.get_db", fail_if_database_opens, raising=False
    )

    with pytest.raises(ValueError, match="requires an exact location_id"):
        agent_class().run()


def test_registered_synthesis_views_match_migration_select_allowlist() -> None:
    base_migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/543_tenant_scoped_agent_synthesis_source_views.sql"
    ).read_text()
    organic_migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/549_signed_organic_readiness_synthesis_source.sql"
    ).read_text()
    ecological_migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/550_signed_ecological_modeling_synthesis_source.sql"
    ).read_text()
    provenance_migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/551_ecological_synthesis_provenance_capacity.sql"
    ).read_text()
    expected_views = set(re.findall(r"'v_public_[a-z0-9_]+'", base_migration))
    expected_views = {view.strip("'") for view in expected_views}
    registered_views = {
        view for agent_class in AGENTS for view in agent_class.source_reference_views.values()
    }

    assert len(expected_views) == 40
    assert len(registered_views) == 60
    assert "CREATE OR REPLACE VIEW kokonut_agent_source." in base_migration
    assert "CREATE OR REPLACE VIEW kokonut_agent_source." in organic_migration
    assert "CREATE OR REPLACE VIEW kokonut_agent_source.ecological_harvest_event" in ecological_migration
    assert "CREATE OR REPLACE VIEW kokonut_agent_source.ecological_species_observation" in ecological_migration
    assert "CREATE OR REPLACE VIEW kokonut_agent_source.harvest_event" not in ecological_migration
    assert "CREATE OR REPLACE VIEW kokonut_agent_source.species_observation" not in ecological_migration
    assert all(
        "'" + view + "'" in base_migration
        or "'" + view + "'" in organic_migration
        or "'" + view + "'" in ecological_migration
        or "'" + view + "'" in provenance_migration
        for view in registered_views
    )
    assert expected_views.issubset(registered_views)


class _OrganicCursor:
    def __init__(self) -> None:
        self.queries: list[tuple[str, Any]] = []
        self.current_query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, query: str, params: Any = None) -> None:
        self.current_query = query
        self.queries.append((query, params))

    def fetchone(self) -> tuple[Any, ...] | None:
        query = self.current_query.lower()
        if "select count(*) from" in " ".join(query.split()):
            return (0,)
        if "from organic_readiness_assessment" in query:
            return None
        if "from organic_input_audit" in query:
            return (0, 0, 0, 0, 0, 0)
        if "from harvest_handling_record" in query:
            return (0, 0, 0, 0, 0, 0, 0)
        if "from prohibited_substance_record" in query:
            return (0, 0, 0, 0, 0, None)
        raise AssertionError(f"unexpected organic readiness query: {self.current_query}")

    def fetchall(self) -> list[tuple[Any, ...]]:
        return []

    def close(self) -> None:
        pass


class _OrganicConnection:
    def __init__(self) -> None:
        self.query_cursor = _OrganicCursor()

    def cursor(self, cursor_factory: Any = None) -> _OrganicCursor:
        return self.query_cursor


def test_organic_readiness_uses_scoped_search_path_and_exact_location_queries() -> None:
    connection = _OrganicConnection()

    OrganicReadinessSynthesisAgent().synthesize(connection, LOCATION_ID)

    assert connection.query_cursor.queries[0] == (
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog",
        None,
    )
    analytics_queries = connection.query_cursor.queries[1:]
    relations = {
        relation
        for query, _ in analytics_queries
        for relation in SYNTHESIS_RELATION.findall(query)
    }
    assert relations == set(OrganicReadinessSynthesisAgent.source_tables)
    assert all(re.match(r"\s*SELECT\b", query, re.IGNORECASE) for query, _ in analytics_queries)
    assert all(params and params[0] == LOCATION_ID for _, params in analytics_queries)


def test_organic_readiness_summary_type_and_registered_worker_are_aligned() -> None:
    from services.agents.worker_cli import resolve_synthesis_agent

    resolved = resolve_synthesis_agent("organic_readiness_synthesis")
    assert isinstance(resolved, OrganicReadinessSynthesisAgent)
    assert resolved.summary_type == "organic_readiness"
    assert resolved.summary_type in SYNTHESIS_SUMMARY_TYPES
    assert get_task("organic_readiness_synthesis")
    assert "organic_compliance_checklist" in resolved.source_tables
    assert "organic_compliance_checklist" not in resolved.source_reference_views


def test_ecological_modeling_summary_type_and_registered_worker_are_aligned() -> None:
    from services.agents.worker_cli import resolve_synthesis_agent

    resolved = resolve_synthesis_agent("ecological_modeling_synthesis")
    assert isinstance(resolved, EcologicalModelingSynthesisAgent)
    assert resolved.summary_type == "ecological_modeling"
    assert resolved.summary_type in SYNTHESIS_SUMMARY_TYPES
    assert get_task("ecological_modeling_synthesis")
    assert len(resolved.source_tables) == 14
    assert len(resolved.source_reference_views) == 13
    assert "location" not in resolved.source_reference_views


class _EcologicalCursor(_OrganicCursor):
    def fetchone(self) -> tuple[Any, ...]:
        return (0,)


class _EcologicalConnection(_OrganicConnection):
    def __init__(self) -> None:
        self.query_cursor = _EcologicalCursor()


def test_ecological_modeling_uses_scoped_search_path_and_exact_location_queries() -> None:
    connection = _EcologicalConnection()

    EcologicalModelingSynthesisAgent().synthesize(connection, LOCATION_ID)

    assert connection.query_cursor.queries[0] == (
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog",
        None,
    )
    analytics_queries = connection.query_cursor.queries[1:]
    relations = {
        relation
        for query, _ in analytics_queries
        for relation in SYNTHESIS_RELATION.findall(query)
    }
    expected_relations = set(EcologicalModelingSynthesisAgent.source_tables)
    expected_relations.difference_update({"harvest_event", "species_observation"})
    expected_relations.update(
        {"ecological_harvest_event", "ecological_species_observation"}
    )
    assert relations == expected_relations
    assert all(
        re.match(r"\s*SELECT\b", query, re.IGNORECASE)
        for query, _ in analytics_queries
    )
    assert all(params == (LOCATION_ID,) for _, params in analytics_queries)


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
def test_location_source_reference_collector_uses_bounded_scoped_views(agent_class: Any) -> None:
    connection = _Connection(list(agent_class.source_reference_views))
    agent = agent_class()

    references = agent.collect_source_references(connection, LOCATION_ID)

    assert set(references) == set(agent.source_reference_views)
    assert all(
        re.search(
            rf"\bFROM\s+kokonut_agent_source\.{re.escape(view)}\b",
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


def test_source_reference_validator_accepts_twenty_registered_sources() -> None:
    source_tables = list(dict.fromkeys(
        source
        for agent_class in AGENTS
        for source in agent_class.source_reference_views
    ))[:20]
    references = {
        table: {
            "record_ids": ["e0000000-0000-4000-8000-000000000001"],
            "row_count": 1,
            "truncated": False,
        }
        for table in source_tables
    }

    validated, _ = _validate_source_references(references, source_tables)

    assert len(validated) == 20


def test_source_reference_validator_rejects_more_than_twenty_registered_sources() -> None:
    source_tables = list(dict.fromkeys(
        source
        for agent_class in AGENTS
        for source in agent_class.source_reference_views
    ))[:21]
    references = {
        table: {
            "record_ids": [f"e0000000-0000-4000-8000-{index:012d}"],
            "row_count": 1,
            "truncated": False,
        }
        for index, table in enumerate(source_tables, start=1)
    }

    with pytest.raises(ValueError, match="at most 20 source tables"):
        _validate_source_references(references, source_tables)


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
    assert "stakeholder_feedback" not in WellbeingSynthesisAgent.source_reference_views
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
