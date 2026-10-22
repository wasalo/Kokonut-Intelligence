"""Focused offline tests for the signed worker AI-summary adapter."""

from __future__ import annotations

import json
from typing import Any

import pytest

from services.agents import worker_draft
from services.agents.worker_draft import SUPPORTED_WORKER_SUMMARY_TYPES, AgentDraftInvalid

LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
REQUEST_ID = "d0000000-0000-4000-8000-000000000001"


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.query = ""

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def execute(self, query: str, params: Any = None) -> None:
        self.query = " ".join(query.split())
        self.connection.calls.append((self.query, params))
        if "set_location_ai_summary_source_references" in self.query:
            self.connection.source_references = json.loads(params[3])

    def fetchone(self) -> tuple[Any, ...] | None:
        if "get_location_ai_summary_worker_result" in self.query:
            return self.connection.lookup_result
        if "create_location_ai_summary_worker_draft" in self.query:
            if self.connection.create_result is not None and "_with_result" not in self.query:
                return self.connection.create_result[:7]
            return self.connection.create_result
        if "get_location_ai_summary_worker_source_references" in self.query:
            return (self.connection.source_references,)
        if "set_location_ai_summary_source_references" in self.query:
            if self.connection.fail_source_setter:
                raise RuntimeError("synthetic source attachment failure")
            return (self.connection.source_references,)
        return None


class FakeConnection:
    autocommit = False

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.lookup_result: tuple[Any, ...] | None = None
        self.source_references: dict[str, Any] = {}
        self.fail_source_setter = False
        self.create_result: tuple[Any, ...] | None = (
            "c0000000-0000-4000-8000-000000000001",
            "Bounded worker draft",
            ["harvest_event"],
            "agent-v2",
            "2026-10-21T00:00:00Z",
            "draft",
            False,
            {
                "location_id": LOCATION_ID,
                "synthesis": "Bounded worker draft",
                "confidence": 0.9,
            },
        )
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("summary_type", sorted(SUPPORTED_WORKER_SUMMARY_TYPES))
def test_registered_worker_summary_types_pass_payload_validation(summary_type: str) -> None:
    content, source_tables, *_ = worker_draft._validate_payload(
        summary_type,
        {"content": "Registered draft", "source_tables": ["harvest_event"]},
    )

    assert content == "Registered draft"
    assert source_tables == ["harvest_event"]


def test_worker_result_is_json_bounded_and_matches_the_draft() -> None:
    result = {
        "content": "Stored draft",
        "measures": {"confidence": 0.8},
    }
    encoded = worker_draft._serialize_worker_result(
        {"worker_result": result}, content="Stored draft"
    )
    assert json.loads(encoded or "null") == result

    with pytest.raises(AgentDraftInvalid, match="must match the stored draft"):
        worker_draft._serialize_worker_result(
            {"worker_result": {"synthesis": "Different draft"}},
            content="Stored draft",
        )
    with pytest.raises(AgentDraftInvalid, match="must match the stored draft"):
        worker_draft._serialize_worker_result(
            {
                "worker_result": {
                    "content": "Stored draft",
                    "synthesis": "Different draft",
                }
            },
            content="Stored draft",
        )
    with pytest.raises(AgentDraftInvalid, match="JSON-compatible"):
        worker_draft._serialize_worker_result(
            {"worker_result": {"content": "Stored draft", "unsupported": object()}},
            content="Stored draft",
        )
    with pytest.raises(AgentDraftInvalid, match="131072-byte limit"):
        worker_draft._serialize_worker_result(
            {"worker_result": {"content": "Stored draft", "extra": "x" * 131072}},
            content="Stored draft",
        )


def test_legacy_worker_result_row_keeps_content_only_fallback() -> None:
    result = worker_draft._read_row(
        (
            "c0000000-0000-4000-8000-000000000003",
            "Legacy draft content",
            ["harvest_event"],
            "agent-v1",
            "2026-10-21T00:00:00Z",
            "draft",
            None,
        ),
        replayed=True,
    )

    assert result is not None
    assert result["content"] == "Legacy draft content"
    assert "worker_result" not in result


def _install_worker_mocks(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    events: list[tuple[Any, ...]] = []
    monkeypatch.setattr(worker_draft, "get_worker_credential", lambda key: "s" * 40)
    monkeypatch.setattr(worker_draft, "set_worker_tenant_context", lambda conn, **kwargs: events.append(("context", conn, kwargs)))
    return events


def test_worker_store_sets_exact_signed_scope_before_bounded_function(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    events = _install_worker_mocks(monkeypatch)
    result = worker_draft.create_worker_ai_summary_draft(
        LOCATION_ID,
        "holistic_wellbeing",
        REQUEST_ID,
        {
            "synthesis": "Bounded worker draft",
            "worker_result": {
                "location_id": LOCATION_ID,
                "synthesis": "Bounded worker draft",
                "confidence": 0.9,
            },
            "source_tables": ["harvest_event"],
            "model_version": "agent-v2",
        },
        connection_factory=lambda: connection,
    )

    assert [event[0] for event in events] == ["context"]
    assert events[0][2] == {
        "credential": "s" * 40,
        "location_id": LOCATION_ID,
        "resource": "ai_summary",
        "action": "draft",
    }
    sql = [query for query, _ in connection.calls]
    assert sql[:2] == ["SET LOCAL statement_timeout = '15s'", "SET LOCAL lock_timeout = '3s'"]
    assert "create_location_ai_summary_worker_draft_with_result" in sql[2]
    assert result["summary_id"] == "c0000000-0000-4000-8000-000000000001"
    assert result["resulting_status"] == "draft"
    assert result["replayed"] is False
    assert result["worker_result"]["confidence"] == 0.9
    assert json.loads(connection.calls[2][1][6])["confidence"] == 0.9
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_worker_lookup_returns_existing_request_before_regeneration(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    connection.lookup_result = (
        "c0000000-0000-4000-8000-000000000002",
        "Existing draft",
        ["sensor_reading"],
        "agent-v1",
        "2026-10-20T00:00:00Z",
        "draft",
        {"content": "Original structured response", "confidence": 0.75},
    )
    _install_worker_mocks(monkeypatch)

    result = worker_draft.get_worker_ai_summary_draft(
        LOCATION_ID,
        "soil_health",
        REQUEST_ID,
        connection_factory=lambda: connection,
    )

    assert result is not None
    assert result["summary_id"] == "c0000000-0000-4000-8000-000000000002"
    assert result["replayed"] is True
    assert len(connection.calls) == 4
    assert "get_location_ai_summary_worker_result" in connection.calls[2][0]
    assert "get_location_ai_summary_worker_source_references" in connection.calls[3][0]
    assert result["worker_result"] == {
        "content": "Original structured response",
        "confidence": 0.75,
    }
    assert connection.commits == 1
    assert connection.closed


@pytest.mark.parametrize(
    ("summary_type", "summary", "message"),
    [
        ("Bad-Type", {"content": "x", "source_tables": ["harvest_event"]}, "summary_type"),
        ("unregistered_agent", {"content": "x", "source_tables": ["harvest_event"]}, "registered worker draft type"),
        ("operations", {"content": " ", "source_tables": ["harvest_event"]}, "summary content"),
        ("operations", {"content": "x", "source_tables": []}, "source_tables"),
        ("operations", {"content": "x", "source_tables": ["bad-name"]}, "source_tables"),
        ("operations", {"content": "x", "source_tables": ["harvest_event"] * 2}, "source_tables"),
        ("operations", {"content": "x", "source_tables": ["harvest_event"], "model_version": "x" * 101}, "model_version"),
    ],
)
def test_invalid_worker_draft_fails_before_secret_or_database_access(
    monkeypatch: pytest.MonkeyPatch,
    summary_type: str,
    summary: dict[str, Any],
    message: str,
) -> None:
    def unexpected(*_: Any, **__: Any) -> Any:
        raise AssertionError("invalid request reached worker secret/database access")

    monkeypatch.setattr(worker_draft, "get_worker_credential", unexpected)
    with pytest.raises(AgentDraftInvalid, match=message):
        worker_draft.create_worker_ai_summary_draft(
            LOCATION_ID,
            summary_type,
            REQUEST_ID,
            summary,
            connection_factory=unexpected,
        )


def test_worker_write_rolls_back_and_closes_on_function_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    _install_worker_mocks(monkeypatch)
    connection.create_result = None

    with pytest.raises(RuntimeError, match="returned no result"):
        worker_draft.create_worker_ai_summary_draft(
            LOCATION_ID,
            "operations",
            REQUEST_ID,
            {"content": "x", "source_tables": ["harvest_event"]},
            connection_factory=lambda: connection,
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed


def test_worker_write_rolls_back_draft_when_source_attachment_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    connection.fail_source_setter = True
    _install_worker_mocks(monkeypatch)

    with pytest.raises(RuntimeError, match="source attachment failure"):
        worker_draft.create_worker_ai_summary_draft(
            LOCATION_ID,
            "operations",
            REQUEST_ID,
            {
                "content": "Draft and lineage must commit atomically",
                "source_tables": ["harvest_event"],
                "source_references": {
                    "harvest_event": {
                        "record_ids": ["e0000000-0000-4000-8000-000000000001"],
                        "row_count": 1,
                        "truncated": False,
                    }
                },
            },
            connection_factory=lambda: connection,
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed


def test_worker_write_attaches_source_references_and_returns_stored_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    _install_worker_mocks(monkeypatch)
    source_references = {
        "harvest_event": {
            "record_ids": ["e0000000-0000-4000-8000-000000000001"],
            "row_count": 1,
            "truncated": False,
        },
        "capital_efficiency_scenario": {
            "record_ids": ["e0000000-0000-4000-8000-000000000201"],
            "row_count": 1,
            "truncated": False,
        },
        "regenerative_efficiency_observation": {
            "record_ids": ["e0000000-0000-4000-8000-000000000211"],
            "row_count": 1,
            "truncated": False,
        },
        "governance_throughput_observation": {
            "record_ids": ["e0000000-0000-4000-8000-000000000221"],
            "row_count": 1,
            "truncated": False,
        },
        "capital_provider_utility_scenario": {
            "record_ids": ["e0000000-0000-4000-8000-000000000231"],
            "row_count": 1,
            "truncated": False,
        },
        "bio_factory_batch": {
            "record_ids": ["e0000000-0000-4000-8000-000000000301"],
            "row_count": 1,
            "truncated": False,
        },
        "bio_input_provenance": {
            "record_ids": ["e0000000-0000-4000-8000-000000000311"],
            "row_count": 1,
            "truncated": False,
        },
        "bio_recipe_library": {
            "record_ids": ["e0000000-0000-4000-8000-000000000321"],
            "row_count": 1,
            "truncated": False,
        },
        "bio_factory_quality_test": {
            "record_ids": ["e0000000-0000-4000-8000-000000000331"],
            "row_count": 1,
            "truncated": False,
        },
    }

    result = worker_draft.create_worker_ai_summary_draft(
        LOCATION_ID,
        "holistic_wellbeing",
        REQUEST_ID,
        {
            "content": "A source-linked worker draft",
            "source_tables": list(source_references),
            "source_references": source_references,
        },
        connection_factory=lambda: connection,
    )

    assert result["source_references"] == source_references
    assert [query.split("(", 1)[0] for query, _ in connection.calls[2:]] == [
        "SELECT * FROM kokonut_security.create_location_ai_summary_worker_draft",
        "SELECT kokonut_security.set_location_ai_summary_source_references",
        "SELECT kokonut_security.get_location_ai_summary_worker_source_references",
    ]
    assert json.loads(connection.calls[3][1][3]) == source_references
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_worker_write_accepts_regenerator_source_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    _install_worker_mocks(monkeypatch)
    source_tables = [
        "regenerative_outcome_summary",
        "community_governance_mechanism",
        "replication_readiness_assessment",
        "adaptive_stewardship_review",
    ]
    source_references = {
        table: {
            "record_ids": [f"e0000000-0000-4000-8000-{index:012d}"],
            "row_count": 1,
            "truncated": False,
        }
        for index, table in enumerate(source_tables, start=401)
    }

    result = worker_draft.create_worker_ai_summary_draft(
        LOCATION_ID,
        "regenerative_outcomes",
        REQUEST_ID,
        {
            "content": "Location-scoped regenerative source references",
            "source_tables": source_tables,
            "source_references": source_references,
        },
        connection_factory=lambda: connection,
    )

    assert result["source_references"] == source_references
    assert json.loads(connection.calls[3][1][3]) == source_references
    assert connection.commits == 1
    assert connection.rollbacks == 0


@pytest.mark.parametrize(
    ("source_references", "message"),
    [
        ({"sensor_reading": {"record_ids": [], "row_count": 0, "truncated": False}}, "declared"),
        ({"unknown_table": {"record_ids": [], "row_count": 0, "truncated": False}}, "declared"),
        ({"harvest_event": {"record_ids": ["not-a-uuid"], "row_count": 1, "truncated": False}}, "UUIDs"),
        ({"harvest_event": {"record_ids": ["e0000000-0000-4000-8000-000000000001"] * 2, "row_count": 2, "truncated": False}}, "unique"),
        ({"harvest_event": {"record_ids": [], "row_count": 1, "truncated": False}}, "inconsistent"),
        ({"harvest_event": {"record_ids": [], "row_count": 0, "truncated": True}}, "inconsistent"),
        ({"harvest_event": {"record_ids": ["e0000000-0000-4000-8000-000000000001"] * 51, "row_count": 51, "truncated": True}}, "at most 50"),
        (
            {
                "harvest_event": {
                    "record_ids": ["e0000000-0000-4000-8000-000000000001"],
                    "row_count": 1,
                    "truncated": False,
                    "scope": "all_tenants",
                }
            },
            "scope is invalid",
        ),
    ],
)
def test_invalid_source_references_fail_before_secret_or_database_access(
    monkeypatch: pytest.MonkeyPatch,
    source_references: dict[str, Any],
    message: str,
) -> None:
    def unexpected(*_: Any, **__: Any) -> Any:
        raise AssertionError("invalid source references reached worker secret/database access")

    monkeypatch.setattr(worker_draft, "get_worker_credential", unexpected)
    with pytest.raises(AgentDraftInvalid, match=message):
        worker_draft.create_worker_ai_summary_draft(
            LOCATION_ID,
            "operations",
            REQUEST_ID,
            {
                "content": "x",
                "source_tables": ["harvest_event"],
                "source_references": source_references,
            },
            connection_factory=unexpected,
        )
