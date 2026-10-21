"""Ensure CSV validation audit rows stay in the caller's location transaction."""

from __future__ import annotations

import csv
from types import SimpleNamespace

import pytest

from services.ingestion import sensor_ingester

LOCATION_ID = "12345678-1234-5678-1234-567812345678"


class _Connection:
    def __init__(self) -> None:
        self.closed = False
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    ("row", "reject_validation"),
    [
        ({"device_id": "", "reading_date": "2026-10-21", "value": "10"}, False),
        ({"device_id": "soil-01", "reading_date": "not-a-date", "value": "10"}, False),
        ({"device_id": "soil-01", "reading_date": "2026-10-21", "value": "10"}, True),
    ],
    ids=["missing-fields", "invalid-timestamp", "rejected-reading"],
)
def test_rejected_csv_row_audit_uses_scoped_caller_connection(
    monkeypatch, tmp_path, row: dict[str, str], reject_validation: bool
) -> None:
    csv_path = tmp_path / "readings.csv"
    with csv_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["device_id", "reading_date", "value"])
        writer.writeheader()
        writer.writerow(row)

    connection = _Connection()
    connections = []
    audit_calls = []
    monkeypatch.setattr(
        sensor_ingester, "get_db", lambda: connections.append(connection) or connection
    )
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        sensor_ingester,
        "log_ingestion",
        lambda **kwargs: audit_calls.append(kwargs),
    )
    if reject_validation:
        monkeypatch.setattr(
            sensor_ingester,
            "get_sensor_by_id_or_slug",
            lambda *_args: ("sensor-id", LOCATION_ID, None, "soil-01", "soil_moisture", LOCATION_ID),
        )
        monkeypatch.setattr(
            sensor_ingester,
            "validate_sensor_reading",
            lambda *_args, **_kwargs: SimpleNamespace(
                status="rejected",
                errors=["value outside range"],
                warnings=[],
                dedupe_key="synthetic-dedupe-key",
            ),
        )

    sensor_ingester.run_csv(str(csv_path), LOCATION_ID)

    assert len(connections) == 1
    assert len(audit_calls) == 1
    assert audit_calls[0]["db"] is connection
    assert audit_calls[0]["location_id"] == LOCATION_ID
    assert connection.commits == 1
    assert connection.closed


def test_successful_csv_row_audit_uses_scoped_caller_connection(monkeypatch, tmp_path) -> None:
    csv_path = tmp_path / "readings.csv"
    with csv_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["device_id", "reading_date", "value"])
        writer.writeheader()
        writer.writerow(
            {"device_id": "soil-01", "reading_date": "2026-10-21", "value": "10"}
        )

    connection = _Connection()
    audit_calls = []
    sensor_info = ("sensor-id", LOCATION_ID, None, "soil-01", "soil_moisture", LOCATION_ID)
    monkeypatch.setattr(sensor_ingester, "get_db", lambda: connection)
    monkeypatch.setattr(sensor_ingester, "get_sensor_type_ranges", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        sensor_ingester, "get_sensor_by_id_or_slug", lambda *_args: sensor_info
    )
    monkeypatch.setattr(
        sensor_ingester,
        "validate_sensor_reading",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="valid", errors=[], warnings=[], dedupe_key="synthetic-dedupe-key"
        ),
    )
    monkeypatch.setattr(sensor_ingester, "insert_reading", lambda *_args, **_kwargs: "reading-id")
    monkeypatch.setattr(sensor_ingester, "insert_reading_clickhouse", lambda *_args: None)
    monkeypatch.setattr(
        sensor_ingester,
        "_get_event_bus",
        lambda **_kwargs: SimpleNamespace(publish=lambda *_args, **_kwargs: None),
    )
    monkeypatch.setattr(
        sensor_ingester,
        "log_ingestion",
        lambda **kwargs: audit_calls.append(kwargs),
    )

    sensor_ingester.run_csv(str(csv_path), LOCATION_ID)

    assert len(audit_calls) == 1
    assert audit_calls[0]["db"] is connection
    assert audit_calls[0]["location_id"] == LOCATION_ID
    assert connection.commits == 1
    assert connection.closed
