"""Graph-projection CLI validates supplied query scope before PostgreSQL."""

from uuid import uuid4

import pytest

from services.graph_projection import cli


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.mark.parametrize("location_id", ["", "not-a-uuid", "1234"])
def test_query_rejects_invalid_location_before_database(monkeypatch, location_id):
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid location must fail before opening PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["query", "--entity-key", "farm:one", "--location-id", location_id])

    assert exc_info.value.code == 2


def test_query_canonicalizes_valid_location_before_query(monkeypatch):
    connection = _Connection()
    location_id = str(uuid4())
    query_calls = []
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli,
        "query_graph",
        lambda *args: query_calls.append(args) or {"nodes": [], "edges": []},
    )
    monkeypatch.setattr(cli, "print_json", lambda _result: None)

    result = cli.main([
        "query", "--entity-key", "farm:one", "--location-id", location_id.upper(),
    ])

    assert result is None
    assert query_calls == [(connection, "farm:one", 1, 100, None, location_id, "internal")]
    assert connection.closed


def test_query_without_location_keeps_global_scope(monkeypatch):
    connection = _Connection()
    query_calls = []
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli,
        "query_graph",
        lambda *args: query_calls.append(args) or {"nodes": [], "edges": []},
    )
    monkeypatch.setattr(cli, "print_json", lambda _result: None)

    cli.main(["query", "--entity-key", "network:one"])

    assert query_calls[0][5] is None
    assert connection.closed


@pytest.mark.parametrize(
    "arguments",
    [
        ["query", "--entity-key", "farm:one", "--depth", "-1"],
        ["query", "--entity-key", "farm:one", "--depth", "6"],
        ["query", "--entity-key", "farm:one", "--node-cap", "0"],
        ["query", "--entity-key", "farm:one", "--node-cap", "501"],
        ["query", "--entity-key", ""],
        ["query", "--entity-key", "farm:one", "--edge-type", "unknown"],
        ["validate", "--generation-id", "not-a-uuid"],
        ["rebuild", "--actor", "   "],
    ],
)
def test_invalid_graph_cli_inputs_fail_before_database(monkeypatch, arguments):
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid graph CLI input must fail before PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(arguments)

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("depth", "node_cap", "edge_type"),
    [(0, 1, "registers"), (5, 500, "attests")],
)
def test_query_accepts_boundaries_and_forwards_supported_filters(
    monkeypatch, depth, node_cap, edge_type
):
    connection = _Connection()
    query_calls = []
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli,
        "query_graph",
        lambda *args: query_calls.append(args) or {"nodes": [], "edges": []},
    )
    monkeypatch.setattr(cli, "print_json", lambda _result: None)

    cli.main(
        [
            "query",
            "--entity-key",
            "farm:one",
            "--depth",
            str(depth),
            "--node-cap",
            str(node_cap),
            "--edge-type",
            edge_type,
        ]
    )

    assert query_calls == [
        (connection, "farm:one", depth, node_cap, [edge_type], None, "internal")
    ]
    assert connection.closed


def test_validate_canonicalizes_valid_generation_uuid_before_database(monkeypatch):
    connection = _Connection()
    generation_id = uuid4()
    validate_calls = []
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli,
        "validate_generation",
        lambda *args: validate_calls.append(args) or {"valid": True, "errors": []},
    )
    monkeypatch.setattr(cli, "print_json", lambda _result: None)

    cli.main(["validate", "--generation-id", str(generation_id).upper()])

    assert validate_calls == [(connection, str(generation_id))]
    assert connection.closed

