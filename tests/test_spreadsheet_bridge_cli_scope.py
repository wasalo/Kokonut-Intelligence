"""CLI scope validation for the spreadsheet bridge."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from services.export import spreadsheet_bridge


def test_export_rejects_malformed_location_before_database(monkeypatch: pytest.MonkeyPatch) -> None:
    get_connection = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(spreadsheet_bridge, "get_connection", get_connection)
    monkeypatch.setattr(
        sys,
        "argv",
        ["spreadsheet_bridge", "--export-file", "activities.csv", "--location-id", "not-a-uuid"],
    )

    with pytest.raises(SystemExit) as error:
        spreadsheet_bridge.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


def test_export_dispatches_valid_location(monkeypatch: pytest.MonkeyPatch) -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    conn = Mock()
    get_connection = Mock(return_value=conn)
    export = Mock(return_value={"exported": 0, "path": "activities.csv"})
    print_json = Mock()
    monkeypatch.setattr(spreadsheet_bridge, "get_connection", get_connection)
    monkeypatch.setattr(spreadsheet_bridge, "export_farm_activity_csv", export)
    monkeypatch.setattr(spreadsheet_bridge, "print_json", print_json)
    monkeypatch.setattr(
        sys,
        "argv",
        ["spreadsheet_bridge", "--export-file", "activities.csv", "--location-id", location_id],
    )

    spreadsheet_bridge.main()

    get_connection.assert_called_once_with()
    export.assert_called_once_with(conn, "activities.csv", location_id)
    conn.close.assert_called_once_with()
    print_json.assert_called_once_with({"exported": 0, "path": "activities.csv"})


def test_help_and_template_remain_database_free(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    get_connection = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(spreadsheet_bridge, "get_connection", get_connection)
    monkeypatch.setattr(spreadsheet_bridge, "print_json", Mock())
    monkeypatch.setattr(sys, "argv", ["spreadsheet_bridge", "--help"])

    with pytest.raises(SystemExit) as error:
        spreadsheet_bridge.main()

    assert error.value.code == 0

    template_path = tmp_path / "template.csv"
    monkeypatch.setattr(sys, "argv", ["spreadsheet_bridge", "--template", str(template_path)])
    spreadsheet_bridge.main()

    assert "location_id" in template_path.read_text()
    get_connection.assert_not_called()


def test_ebf_evidence_dry_run_remains_database_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csv_path = tmp_path / "evidence.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["scorecard_id", "pillar_key", "evidence_type", "evidence_id"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "scorecard_id": "scorecard-1",
                "pillar_key": "soil_health",
                "evidence_type": "metric_value",
                "evidence_id": "metric-1",
            }
        )

    get_connection = Mock(side_effect=AssertionError("database must not be opened"))
    print_json = Mock()
    monkeypatch.setattr(spreadsheet_bridge, "get_connection", get_connection)
    monkeypatch.setattr(spreadsheet_bridge, "print_json", print_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "spreadsheet_bridge",
            "--import-file",
            str(csv_path),
            "--template-type",
            "ebf_evidence",
            "--dry-run",
        ],
    )

    spreadsheet_bridge.main()

    get_connection.assert_not_called()
    print_json.assert_called_once_with(
        {"validated": 1, "errors": [], "template_type": "ebf_evidence"}
    )
