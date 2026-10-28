"""Management work-item CLI location scope is validated before opening PostgreSQL."""

from uuid import uuid4

import pytest

from services.management import cli


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


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
    assert connection.closed

