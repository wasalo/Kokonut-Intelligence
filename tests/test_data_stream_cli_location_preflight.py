"""Data Stream CLI location UUIDs fail before a database connection opens."""

import sys

import pytest

from services.data_stream import cli as data_stream_cli

LOCATION_ID = "A0000000-0000-4000-8000-000000000001"
CANONICAL_LOCATION_ID = "a0000000-0000-4000-8000-000000000001"
LOCATION_COMMANDS = ("post", "stream", "list", "search")


def _argv(command: str, *location_args: str) -> list[str]:
    args = ["data-stream", command]
    if command == "post":
        args.extend(["--title", "Test post"])
    elif command == "search":
        args.extend(["--query", "soil"])
    args.extend(location_args)
    return args


@pytest.mark.parametrize("command", LOCATION_COMMANDS)
@pytest.mark.parametrize("location_id", ["not-a-uuid", ""])
def test_location_commands_reject_malformed_uuid_before_connection(
    monkeypatch, command, location_id
):
    monkeypatch.setattr(
        data_stream_cli,
        "get_connection",
        lambda: pytest.fail("malformed location must fail before a DB connection"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _argv(command, "--location-id", location_id),
    )

    with pytest.raises(SystemExit) as exc_info:
        data_stream_cli.main()

    assert exc_info.value.code == 2


@pytest.mark.parametrize("command", LOCATION_COMMANDS)
def test_location_commands_canonicalize_uuid_before_handler(
    monkeypatch, command
):
    calls = []
    handler_name = {
        "post": "cmd_post",
        "stream": "cmd_stream",
        "list": "cmd_list",
        "search": "cmd_search",
    }[command]
    monkeypatch.setattr(
        data_stream_cli,
        handler_name,
        lambda args: calls.append(args.location_id),
    )
    monkeypatch.setattr(data_stream_cli, "get_connection", lambda: pytest.fail("handler stub expected"))
    monkeypatch.setattr(
        sys,
        "argv",
        _argv(command, "--location-id", LOCATION_ID),
    )

    data_stream_cli.main()

    assert calls == [CANONICAL_LOCATION_ID]


def test_search_without_location_preserves_unfiltered_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(
        data_stream_cli,
        "cmd_search",
        lambda args: calls.append(args.location_id),
    )
    monkeypatch.setattr(data_stream_cli, "get_connection", lambda: pytest.fail("handler stub expected"))
    monkeypatch.setattr(sys, "argv", _argv("search", "--query", "soil"))

    data_stream_cli.main()

    assert calls == [None]
