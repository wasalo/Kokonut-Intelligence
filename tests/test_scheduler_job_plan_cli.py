"""Offline contracts for scheduler job-plan CLI inputs."""

import json
import sys
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.common import database
from services.scheduler.cli import main


def _run_cli(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["kokonut-scheduler", *arguments])
    with pytest.raises(SystemExit) as exit_info:
        main()
    return exit_info.value.code


def test_sensor_job_plan_cli_forwards_required_location_and_driver_instance(monkeypatch, capsys):
    location_id = str(uuid4())
    driver_instance_id = str(uuid4())

    assert _run_cli(
        monkeypatch,
        [
            "--job-plan",
            "sensors",
            "--location-id",
            location_id,
            "--driver-instance-id",
            driver_instance_id,
        ],
    ) == 0

    output = json.loads(capsys.readouterr().out)
    task = output["scheduled_task"]
    assert output["activation_ready"] is False
    assert task["is_enabled"] is False
    assert task["command_args"] == [
        "--location-id",
        location_id,
        "--driver-instance-id",
        driver_instance_id,
    ]


def test_sensor_job_plan_cli_rejects_missing_driver_before_database_access(monkeypatch, capsys):
    database_access = Mock(side_effect=AssertionError("job planning must stay offline"))
    monkeypatch.setattr(database, "get_db", database_access)
    monkeypatch.setattr(database, "get_connection", database_access)

    assert _run_cli(
        monkeypatch,
        ["--job-plan", "sensors", "--location-id", str(uuid4())],
    ) == 1

    captured = capsys.readouterr()
    assert "Error: Sensors schedule planning requires one driver instance" in captured.err
    assert captured.out == ""
    database_access.assert_not_called()
