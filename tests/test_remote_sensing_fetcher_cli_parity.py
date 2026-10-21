"""Synthetic standalone/unified parity for remote-sensing job inventory reads."""

import json

import pytest

from services.ingestion import remote_sensing_fetcher

LOCATION_ID = "12345678-1234-5678-1234-567812345678"


class _Cursor:
    def __init__(self, rows, fail_execute=False):
        self.rows = rows
        self.fail_execute = fail_execute
        self.query = None
        self.params = None
        self.closed = False

    def execute(self, query, params=None):
        self.query = query
        self.params = params
        if self.fail_execute:
            raise RuntimeError("synthetic insert failure")

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, rows, fail_execute=False):
        self.cursor_instance = _Cursor(rows, fail_execute=fail_execute)
        self.closed = False
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def close(self):
        self.closed = True

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_remote_sensing_job_list_output_matches_and_binds_location(monkeypatch, capsys):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    row = {
        "id": "synthetic-job-id",
        "location_id": LOCATION_ID,
        "provider": "gee",
        "status": "active",
        "location_name": "Synthetic farm",
    }
    connections = []

    def make_connection():
        connection = _Connection([row])
        connections.append(connection)
        return connection

    monkeypatch.setattr(remote_sensing_fetcher, "get_db", make_connection)
    arguments = ["--list-jobs", "--location-id", LOCATION_ID]

    remote_sensing_fetcher.main(arguments)
    standalone_output = capsys.readouterr().out
    unified = CliRunner().invoke(
        unified_cli.app,
        ["ingestion", "--", "remote_sensing_fetcher", *arguments],
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == [row]
    assert len(connections) == 2
    for connection in connections:
        assert connection.closed
        assert connection.cursor_instance.closed
        assert "WHERE j.location_id = %s" in connection.cursor_instance.query
        assert connection.cursor_instance.params == (LOCATION_ID,)
    assert unified.stderr == ""


@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
@pytest.mark.parametrize("location_id", [None, "not-a-uuid"])
def test_remote_sensing_job_list_rejects_invalid_scope_before_database(
    monkeypatch, entrypoint, location_id
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    monkeypatch.setattr(
        remote_sensing_fetcher,
        "get_db",
        lambda: pytest.fail("invalid job-list scope must fail before DB setup"),
    )
    arguments = ["--list-jobs"]
    if location_id is not None:
        arguments.extend(["--location-id", location_id])

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            remote_sensing_fetcher.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(
            unified_cli.app,
            ["ingestion", "--", "remote_sensing_fetcher", *arguments],
        )
        assert result.exit_code == 2
        assert "location_id" in result.output.lower()


def test_remote_sensing_job_create_output_and_insert_match_across_clis(
    monkeypatch, capsys
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    connections = []

    def make_connection():
        connection = _Connection([("synthetic-job-id",)])
        connections.append(connection)
        return connection

    monkeypatch.setattr(remote_sensing_fetcher, "get_db", make_connection)
    arguments = [
        "--location-id",
        LOCATION_ID,
        "--provider",
        "copernicus",
        "--cadence-days",
        "14",
    ]

    remote_sensing_fetcher.main(arguments)
    standalone_output = capsys.readouterr().out
    unified = CliRunner().invoke(
        unified_cli.app,
        ["ingestion", "--", "remote_sensing_fetcher", *arguments],
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == {
        "job_id": "synthetic-job-id",
        "status": "created",
    }
    assert len(connections) == 2
    for connection in connections:
        assert connection.closed
        assert connection.cursor_instance.closed
        assert "INSERT INTO remote_sensing_job" in connection.cursor_instance.query
        assert connection.cursor_instance.params == (LOCATION_ID, "copernicus", 14)
        assert connection.commit_count == 1
        assert connection.rollback_count == 0
    assert unified.stderr == ""


@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
@pytest.mark.parametrize("cadence_days", [0, -1])
def test_remote_sensing_job_create_rejects_nonpositive_cadence_before_database(
    monkeypatch, entrypoint, cadence_days
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    monkeypatch.setattr(
        remote_sensing_fetcher,
        "get_db",
        lambda: pytest.fail("invalid cadence must fail before DB setup"),
    )
    arguments = [
        "--location-id",
        LOCATION_ID,
        "--cadence-days",
        str(cadence_days),
    ]

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            remote_sensing_fetcher.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(
            unified_cli.app,
            ["ingestion", "--", "remote_sensing_fetcher", *arguments],
        )
        assert result.exit_code == 2
        assert "positive integer" in result.output


def test_remote_sensing_job_create_rolls_back_and_closes_on_insert_failure(
    monkeypatch,
):
    connection = _Connection([], fail_execute=True)
    monkeypatch.setattr(remote_sensing_fetcher, "get_db", lambda: connection)

    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        remote_sensing_fetcher.main(["--location-id", LOCATION_ID])

    assert connection.closed
    assert connection.cursor_instance.closed
    assert connection.commit_count == 0
    assert connection.rollback_count == 1
