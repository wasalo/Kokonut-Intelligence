"""Fork-event CLI location filters fail before PostgreSQL opens."""

import sys

import pytest

from services.events import cli as events_cli

FORK_LOCATION = "A0000000-0000-4000-8000-000000000001"
CANONICAL_FORK_LOCATION = "a0000000-0000-4000-8000-000000000001"
OPERATIONS = ("--fork-opportunities", "--propose-fork")


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("location_id", ["not-a-uuid", ""])
def test_fork_cli_rejects_malformed_location_before_connection(
    monkeypatch, operation, location_id
):
    monkeypatch.setattr(
        events_cli,
        "_get_conn",
        lambda: pytest.fail("malformed location must fail before PostgreSQL opens"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["events", operation, "--location-id", location_id],
    )

    with pytest.raises(SystemExit) as exc_info:
        events_cli.main()

    assert exc_info.value.code == 2


@pytest.mark.parametrize("operation", OPERATIONS)
def test_fork_cli_canonicalizes_location_before_query(monkeypatch, operation):
    connection = object()
    calls = []
    monkeypatch.setattr(events_cli, "_get_conn", lambda: connection)

    if operation == "--fork-opportunities":
        monkeypatch.setattr(
            "services.events.fork_detector.detect_fork_opportunities",
            lambda conn, *, location_id: calls.append((conn, location_id)) or [],
        )
    else:
        monkeypatch.setattr(
            "services.events.fork_detector.propose_fork_opportunities",
            lambda conn, *, location_id, actor: calls.append((conn, location_id, actor)) or {},
        )

    monkeypatch.setattr(
        sys,
        "argv",
        ["events", operation, "--location-id", FORK_LOCATION],
    )

    with pytest.raises(SystemExit) as exc_info:
        events_cli.main()

    assert exc_info.value.code == 0
    expected = (connection, CANONICAL_FORK_LOCATION)
    assert calls == [expected if operation == "--fork-opportunities" else (*expected, "cli")]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_fork_cli_omitted_location_preserves_all_scope_mode(monkeypatch, operation):
    connection = object()
    calls = []
    monkeypatch.setattr(events_cli, "_get_conn", lambda: connection)

    if operation == "--fork-opportunities":
        monkeypatch.setattr(
            "services.events.fork_detector.detect_fork_opportunities",
            lambda conn, *, location_id: calls.append((conn, location_id)) or [],
        )
    else:
        monkeypatch.setattr(
            "services.events.fork_detector.propose_fork_opportunities",
            lambda conn, *, location_id, actor: calls.append((conn, location_id, actor)) or {},
        )

    monkeypatch.setattr(sys, "argv", ["events", operation])

    with pytest.raises(SystemExit) as exc_info:
        events_cli.main()

    assert exc_info.value.code == 0
    expected = (connection, None)
    assert calls == [expected if operation == "--fork-opportunities" else (*expected, "cli")]

