"""Synthetic standalone/unified parity for scoped remote-sensing CSV imports."""

import csv
from uuid import UUID

import pytest

from services.ingestion import remote_sensing

LOCATION_ID = "12345678-1234-5678-1234-567812345678"
PLOT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor([(UUID(PLOT_ID), UUID(LOCATION_ID))])
        self.closed = False
        self.commit_count = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commit_count += 1

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("scope_arguments", "all_locations"),
    [
        (["--location-id", LOCATION_ID], False),
        (["--all-locations"], True),
    ],
)
def test_remote_sensing_csv_cli_parity_and_scope(
    monkeypatch, tmp_path, scope_arguments, all_locations
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    csv_path = tmp_path / "observations.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "plot_id",
                "location_id",
                "observation_date",
                "source",
                "ndvi",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "plot_id": PLOT_ID,
                "location_id": LOCATION_ID,
                "observation_date": "2026-10-21",
                "source": "drone",
                "ndvi": "0.5",
            }
        )

    connections = []
    records = []
    logs = []

    def make_connection():
        connection = _Connection()
        connections.append(connection)
        return connection

    def insert_record(connection, record):
        records.append((connection, dict(record)))
        return "synthetic-observation-id"

    def record_info(message, *args):
        logs.append(message % args if args else message)

    monkeypatch.setattr(remote_sensing, "get_db", make_connection)
    monkeypatch.setattr(remote_sensing, "insert_observation", insert_record)
    monkeypatch.setattr(remote_sensing, "insert_clickhouse", lambda *_args: None)
    monkeypatch.setattr(remote_sensing, "log_ingestion", lambda **_kwargs: None)
    monkeypatch.setattr(remote_sensing.logger, "info", record_info)

    arguments = ["--file", str(csv_path), *scope_arguments]
    assert remote_sensing.main(arguments) == 0
    standalone_logs = list(logs)
    standalone_records = list(records)
    logs.clear()
    records.clear()
    unified = CliRunner().invoke(
        unified_cli.app, ["ingestion", "--", "remote_sensing", *arguments]
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == ""
    assert logs == standalone_logs
    assert len(connections) == 2
    assert len(standalone_records) == len(records) == 1
    for connection in connections:
        assert connection.closed
        assert connection.commit_count == 1
        assert connection.cursor_instance.closed
        assert "p.id = ANY(%s)" in connection.cursor_instance.query
        if all_locations:
            assert "f.location_id = %s" not in connection.cursor_instance.query
            assert connection.cursor_instance.params == ([PLOT_ID],)
        else:
            assert "f.location_id = %s" in connection.cursor_instance.query
            assert connection.cursor_instance.params == (LOCATION_ID, [PLOT_ID])

    for connection, record in [*standalone_records, *records]:
        assert record["plot_id"] == PLOT_ID
        assert record["location_id"] == LOCATION_ID
        assert record["source_system"] == "csv_upload"
        assert connection in connections
