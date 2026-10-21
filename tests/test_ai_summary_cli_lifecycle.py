"""The standalone AI-summary CLI validates before opening database resources."""

from __future__ import annotations

import sys

import pytest

from services.agents import ai_summary

LOCATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUMMARY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class Cursor:
    def __init__(self, *, fail_on_execute: bool = False, row=None) -> None:
        self.fail_on_execute = fail_on_execute
        self.row = row
        self.closed = False
        self.queries = []

    def execute(self, _query, _parameters=None) -> None:
        self.queries.append(_query)
        if self.fail_on_execute:
            raise RuntimeError("synthetic summary query failure")

    def fetchone(self):
        return self.row

    def close(self) -> None:
        self.closed = True


class Connection:
    def __init__(self, *, fail_on_execute: bool = False, row=None) -> None:
        self.cursor_instance = Cursor(fail_on_execute=fail_on_execute, row=row)
        self.closed = False

    def cursor(self, **_kwargs) -> Cursor:
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


def _set_argv(monkeypatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["ai_summary", *arguments])


def test_missing_mode_fails_before_opening_database(monkeypatch, capsys) -> None:
    _set_argv(monkeypatch)
    monkeypatch.setattr(
        ai_summary, "get_pg", lambda: pytest.fail("database opened before CLI validation")
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()

    assert "--location-id is required" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    [
        ("--location-id", "not-a-uuid"),
        ("--list", "--location-id", "not-a-uuid"),
        ("--verify", "not-a-uuid"),
    ],
)
def test_malformed_identifier_fails_before_opening_database(monkeypatch, arguments) -> None:
    _set_argv(monkeypatch, *arguments)
    monkeypatch.setattr(
        ai_summary, "get_pg", lambda: pytest.fail("database opened before UUID validation")
    )

    with pytest.raises(SystemExit, match="2"):
        ai_summary.main()


def test_summary_generation_does_not_open_a_discarded_connection(monkeypatch, capsys) -> None:
    _set_argv(monkeypatch, "--location-id", LOCATION_ID)
    monkeypatch.setattr(
        ai_summary, "get_pg", lambda: pytest.fail("CLI opened a redundant database connection")
    )
    monkeypatch.setattr(
        ai_summary,
        "run_ai_summary",
        lambda location_id, summary_type, store=False: {
            "summary": {
                "summary_type": summary_type,
                "source_tables": ["harvest_event"],
                "content": "Synthetic summary",
            }
        },
    )

    ai_summary.main()

    assert "Generating combined summary" in capsys.readouterr().out


def test_list_closes_connection_when_query_fails(monkeypatch) -> None:
    _set_argv(monkeypatch, "--list")
    connection = Connection(fail_on_execute=True)
    monkeypatch.setattr(ai_summary, "get_pg", lambda: connection)

    with pytest.raises(RuntimeError, match="synthetic summary query failure"):
        ai_summary.main()

    assert connection.cursor_instance.closed is True
    assert connection.closed is True


def test_verify_closes_cursor_and_connection_when_query_fails(monkeypatch) -> None:
    _set_argv(monkeypatch, "--verify", SUMMARY_ID)
    connection = Connection(fail_on_execute=True)
    monkeypatch.setattr(ai_summary, "get_pg", lambda: connection)

    with pytest.raises(RuntimeError, match="synthetic summary query failure"):
        ai_summary.main()

    assert connection.cursor_instance.closed is True
    assert connection.closed is True


def test_verify_is_explicitly_read_only_and_does_not_claim_lifecycle_review(
    monkeypatch, capsys
) -> None:
    _set_argv(monkeypatch, "--verify", SUMMARY_ID)
    connection = Connection(
        row={
            "id": SUMMARY_ID,
            "summary_type": "operations",
            "status": "draft",
            "model_version": "synthetic-v1",
            "content": "Synthetic summary",
        }
    )
    monkeypatch.setattr(ai_summary, "get_pg", lambda: connection)

    ai_summary.main()

    output = capsys.readouterr().out
    assert "Lifecycle verification: not performed (read-only inspection)" in output
    assert "Content SHA-256 (computed only; not compared):" in output
    assert connection.cursor_instance.queries == ["SELECT * FROM ai_summary WHERE id = %s"]
    assert connection.cursor_instance.closed is True
    assert connection.closed is True
