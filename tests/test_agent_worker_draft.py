"""Focused offline tests for the signed worker AI-summary adapter."""

from __future__ import annotations

from typing import Any

import pytest

from services.agents import worker_draft
from services.agents.worker_draft import AgentDraftInvalid

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

    def fetchone(self) -> tuple[Any, ...] | None:
        if "get_location_ai_summary_worker_draft_request" in self.query:
            return self.connection.lookup_result
        if "create_location_ai_summary_worker_draft" in self.query:
            return self.connection.create_result
        return None


class FakeConnection:
    autocommit = False

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.lookup_result: tuple[Any, ...] | None = None
        self.create_result: tuple[Any, ...] | None = (
            "c0000000-0000-4000-8000-000000000001",
            "Bounded worker draft",
            ["harvest_event"],
            "agent-v2",
            "2026-10-21T00:00:00Z",
            "draft",
            False,
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
        "wellbeing",
        REQUEST_ID,
        {
            "synthesis": "Bounded worker draft",
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
    assert "create_location_ai_summary_worker_draft" in sql[2]
    assert result["summary_id"] == "c0000000-0000-4000-8000-000000000001"
    assert result["resulting_status"] == "draft"
    assert result["replayed"] is False
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
    assert len(connection.calls) == 3
    assert "get_location_ai_summary_worker_draft_request" in connection.calls[2][0]
    assert connection.commits == 1
    assert connection.closed


@pytest.mark.parametrize(
    ("summary_type", "summary", "message"),
    [
        ("Bad-Type", {"content": "x", "source_tables": ["harvest_event"]}, "summary_type"),
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
