"""Management work-item CLI and service inputs fail before PostgreSQL access."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.management import cli, workbench


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _WorkItemCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.connection.row


class _WorkItemConnection:
    def __init__(self):
        self.operations = []
        self.row = {"id": uuid4(), "status": "draft"}
        self.committed = False

    def cursor(self, **_kwargs):
        return _WorkItemCursor(self)

    def commit(self):
        self.committed = True


@pytest.mark.parametrize("location_id", ["", "not-a-uuid", "1234"])
def test_work_item_create_rejects_invalid_location_before_database(monkeypatch, location_id):
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid location must fail before opening PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main([
            "work-item", "create", "--org-id", str(uuid4()), "--title", "Field work",
            "--location-id", location_id,
        ])

    assert exc_info.value.code == 2


def test_work_item_create_canonicalizes_valid_location_before_service(monkeypatch):
    connection = _Connection()
    calls = []
    location_id = str(uuid4())
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli.workbench,
        "create_work_item",
        lambda conn, **kwargs: calls.append((conn, kwargs)) or {},
    )
    monkeypatch.setattr(cli, "_dump", lambda _rows: None)

    result = cli.main([
        "work-item", "create", "--org-id", str(uuid4()), "--title", "Field work",
        "--location-id", location_id.upper(),
    ])

    assert result == 0
    assert calls[0][0] is connection
    assert calls[0][1]["location_id"] == location_id
    assert connection.closed


def test_work_item_create_keeps_location_optional(monkeypatch):
    connection = _Connection()
    calls = []
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli.workbench,
        "create_work_item",
        lambda conn, **kwargs: calls.append((conn, kwargs)) or {},
    )
    monkeypatch.setattr(cli, "_dump", lambda _rows: None)

    cli.main(["work-item", "create", "--org-id", str(uuid4()), "--title", "Network task"])

    assert calls[0][1]["location_id"] is None
    assert calls[0][1]["due_at"] is None
    assert calls[0][1]["sla_at"] is None
    assert connection.closed


@pytest.mark.parametrize("option", ["--due-at", "--sla-at"])
@pytest.mark.parametrize(
    "value",
    ["not-a-timestamp", "2026-10-30T12:00:00", "2026-02-30T12:00:00Z"],
)
def test_work_item_create_rejects_invalid_timestamps_before_database(
    monkeypatch, option, value
):
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid work-item timestamp opened PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main([
            "work-item", "create", "--org-id", str(uuid4()), "--title", "Field work",
            option, value,
        ])

    assert exc_info.value.code == 2


def test_work_item_create_passes_aware_due_and_sla_datetimes(monkeypatch):
    connection = _Connection()
    calls = []
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli.workbench,
        "create_work_item",
        lambda conn, **kwargs: calls.append((conn, kwargs)) or {},
    )
    monkeypatch.setattr(cli, "_dump", lambda _rows: None)

    result = cli.main([
        "work-item", "create", "--org-id", str(uuid4()), "--title", "Field work",
        "--due-at", "2026-10-30T12:00:00Z",
        "--sla-at", "2026-10-30T12:00:00-04:00",
    ])

    assert result == 0
    assert calls[0][0] is connection
    assert calls[0][1]["due_at"] == datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    assert calls[0][1]["sla_at"] == datetime.fromisoformat("2026-10-30T12:00:00-04:00")
    assert connection.closed


@pytest.mark.parametrize("field", ["due_at", "sla_at"])
@pytest.mark.parametrize("value", ["not-a-timestamp", "2026-10-30T12:00:00"])
def test_workbench_rejects_invalid_timestamps_before_opening_database(
    monkeypatch, field, value
):
    monkeypatch.setattr(
        workbench,
        "get_db",
        lambda: pytest.fail("invalid work-item timestamp opened PostgreSQL"),
    )

    with pytest.raises(ValueError, match="timestamp"):
        workbench.create_work_item(
            None,
            str(uuid4()),
            "Field work",
            "system",
            **{field: value},
        )


def test_workbench_accepts_aware_timestamps_and_binds_datetimes():
    connection = _WorkItemConnection()
    due_at = "2026-10-30T12:00:00Z"
    sla_at = datetime.fromisoformat("2026-10-30T12:30:00-04:00")

    workbench.create_work_item(
        connection,
        str(uuid4()),
        "Field work",
        "system",
        due_at=due_at,
        sla_at=sla_at,
    )

    insert_sql, params = connection.operations[0]
    assert "INSERT INTO work_item" in insert_sql
    assert params[-2:] == (
        datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
        sla_at,
    )
    assert connection.committed

