"""Threatcasting CLI validates supplied location scope before database access."""

import sys

import pytest

from services.threatcasting import cli

_INVALID_LOCATION = "not-a-location-uuid"
_VALID_LOCATION = "b0000000-0000-4000-8000-000000000001"
_NARRATIVE_ID = "a0000000-0000-4000-8000-000000000001"


LOCATION_COMMANDS = (
    ["create-threat", "--location-id", _INVALID_LOCATION, "--name", "Drought", "--type", "climate"],
    ["list-threats", "--location-id", _INVALID_LOCATION],
    ["cross-impact", "--location-id", _INVALID_LOCATION],
    ["list-flags", "--location-id", _INVALID_LOCATION],
    ["flag-status", "--location-id", _INVALID_LOCATION],
    ["ingest-signal", "--source", "test", "--content", "signal", "--location-id", _INVALID_LOCATION],
    ["list-signals", "--location-id", _INVALID_LOCATION],
    ["list-narratives", "--location-id", _INVALID_LOCATION],
    ["create-horizon", "--location-id", _INVALID_LOCATION, "--name", "Horizon", "--years", "5"],
    ["create-backcast", "--narrative-id", _NARRATIVE_ID, "--location-id", _INVALID_LOCATION,
     "--name", "Plan", "--future-state", "Future", "--gaps", "Gap"],
    ["cascade-risk", "--location-id", _INVALID_LOCATION],
    ["intelligence", "--location-id", _INVALID_LOCATION],
    ["briefing", "--location-id", _INVALID_LOCATION],
    ["landscape", "--location-id", _INVALID_LOCATION],
    ["create-principle", "--narrative-id", _NARRATIVE_ID, "--location-id", _INVALID_LOCATION,
     "--name", "Principle", "--description", "Description"],
    ["list-principles", "--location-id", _INVALID_LOCATION],
    ["compare-paths", "--location-id", _INVALID_LOCATION, "--name", "Comparison",
     "--narrative-ids", _NARRATIVE_ID],
    ["list-comparisons", "--location-id", _INVALID_LOCATION],
    ["forecast-question-create", "--location-id", _INVALID_LOCATION, "--domain", "climate",
     "--question", "Question", "--event-definition", "Event", "--resolution-criteria", "Criteria",
     "--resolution-source", "Source", "--opens-at", "2026-01-01T00:00:00",
     "--closes-at", "2026-02-01T00:00:00", "--resolves-by", "2026-03-01T00:00:00",
     "--created-by", "operator"],
    ["preempt", "--location-id", _INVALID_LOCATION],
    ["preempt-double-check", "--location-id", _INVALID_LOCATION],
    ["propose-double-check", "--location-id", _INVALID_LOCATION],
)


@pytest.mark.parametrize("arguments", LOCATION_COMMANDS)
def test_every_supplied_location_scope_fails_before_database_open(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["threatcasting", *arguments])
    monkeypatch.setattr(
        cli,
        "_get_conn",
        lambda: pytest.fail("invalid location scope must fail before opening PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


class _Cursor:
    description = [("id",), ("threat_name",)]

    def __init__(self):
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchall(self):
        return []

    def close(self):
        pass


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_valid_location_is_canonicalized_before_query(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(cli, "_get_conn", lambda: connection)
    monkeypatch.setattr(
        sys,
        "argv",
        ["threatcasting", "list-threats", "--location-id", _VALID_LOCATION.upper()],
    )

    cli.main()

    assert "location_id = %s" in connection.cursor_instance.query
    assert connection.cursor_instance.params == [_VALID_LOCATION]
    assert connection.closed


def test_omitted_optional_location_filter_retains_global_list_behavior(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(cli, "_get_conn", lambda: connection)
    monkeypatch.setattr(sys, "argv", ["threatcasting", "list-threats"])

    cli.main()

    assert "location_id = %s" not in connection.cursor_instance.query
    assert connection.cursor_instance.params == []
    assert connection.closed
