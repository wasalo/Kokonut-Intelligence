"""Manual climate selectors remain location-bound and use the signed worker."""

import json
import sys
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from services.ingestion import climate_data


def test_invalid_location_fails_before_worker_or_database_access(monkeypatch):
    run = patch.object(
        climate_data.subprocess,
        "run",
        side_effect=AssertionError("invalid location must fail before worker dispatch"),
    )
    with run, pytest.raises(SystemExit) as exc:
        climate_data.main(["--worldclim", "--location-id", "not-a-uuid"])

    assert exc.value.code == 2


def test_cli_forwards_canonical_location_and_exact_worker_credentials(monkeypatch, capsys):
    location_id = str(uuid4())
    canonical_location_id = str(UUID(location_id))
    report = {
        "status": "success",
        "location_id": canonical_location_id,
        "results": {"modis_lst": {"status": "success", "record_id": "synthetic"}},
        "success": 1,
        "skipped": 0,
        "failed": 0,
        "total": 1,
    }
    completed = type(
        "Completed",
        (),
        {"stdout": json.dumps(report), "returncode": 0},
    )()
    environment_calls = []
    monkeypatch.setattr(climate_data, "is_enabled", lambda _feature: True)

    def worker_environment(**kwargs):
        environment_calls.append(kwargs)
        return {"PATH": "/usr/bin"}

    monkeypatch.setattr(climate_data, "worker_subprocess_environment", worker_environment)
    with patch.object(climate_data.subprocess, "run", return_value=completed) as run:
        result = climate_data.main(["--modis", "--location-id", location_id.upper()])

    assert result == 0
    assert json.loads(capsys.readouterr().out) == report["results"]["modis_lst"]
    run.assert_called_once()
    command = run.call_args.args[0]
    assert command == [
        sys.executable,
        "-m",
        "services.ingestion.climate_worker",
        "--location-id",
        canonical_location_id,
        "--source",
        "modis_lst",
    ]
    assert run.call_args.kwargs["env"] == {"PATH": "/usr/bin"}
    assert environment_calls == [{
        "allowed_worker_keys": ("climate",),
        "isolated_database_credentials": True,
    }]


def test_cli_rejects_conflicting_dataset_modes_before_worker_dispatch():
    with (
        patch.object(climate_data.subprocess, "run") as run,
        pytest.raises(SystemExit) as exc,
    ):
        climate_data.main(["--all", "--worldclim", "--location-id", str(uuid4())])

    assert exc.value.code == 2
    run.assert_not_called()


def test_no_dataset_mode_prints_help_without_worker_dispatch(capsys):
    with patch.object(climate_data.subprocess, "run") as run:
        result = climate_data.main(["--location-id", str(uuid4())])

    assert result == 1
    assert "--worldclim" in capsys.readouterr().out
    run.assert_not_called()


def test_malformed_worker_report_fails_closed(monkeypatch):
    completed = type(
        "Completed",
        (),
        {"stdout": json.dumps({"status": "success", "location_id": "other"}), "returncode": 0},
    )()
    monkeypatch.setattr(climate_data, "is_enabled", lambda _feature: True)
    monkeypatch.setattr(climate_data, "worker_subprocess_environment", lambda **_kwargs: {})
    monkeypatch.setattr(climate_data.subprocess, "run", lambda *_args, **_kwargs: completed)

    report = climate_data._dispatch_signed_climate_worker(str(uuid4()), "modis_lst")

    assert report["status"] == "error"
    assert "invalid result" not in report.get("message", "")
    assert report["message"] == "signed climate worker failed"
