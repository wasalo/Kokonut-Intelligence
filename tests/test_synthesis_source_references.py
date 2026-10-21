"""Shared source-manifest collection for safe synthesis views."""

from __future__ import annotations

from typing import Any

import pytest

from services.agents.commons_agent import CommonsSynthesisAgent
from services.agents.gnh_agent import GnhSynthesisAgent
from services.agents.open_source_capitalist_agent import OpenSourceCapitalistSynthesisAgent
from services.agents.resilience_agent import ResilienceSynthesisAgent
from services.agents.worker_draft import _validate_source_references

AGENTS = [
    CommonsSynthesisAgent,
    GnhSynthesisAgent,
    ResilienceSynthesisAgent,
    OpenSourceCapitalistSynthesisAgent,
]
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


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
    assert all(f"public.{view}" in connection.cursor_value.query for view in agent.source_reference_views.values())
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
    assert "network_scaling_target" not in OpenSourceCapitalistSynthesisAgent.source_reference_views
    assert "open_source_impact_artifact" not in OpenSourceCapitalistSynthesisAgent.source_reference_views
    assert "green_paper_publication_review" not in ResilienceSynthesisAgent.source_reference_views
