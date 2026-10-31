"""Standalone/unified parity for climate selectors routed to the signed worker."""

import json
from types import SimpleNamespace

import pytest

from services.ingestion import climate_data

LOCATION_ID = "12345678-1234-5678-1234-567812345678"
SOURCE_BY_SELECTOR = {
    "--worldclim": "worldclim",
    "--ncep": "era5_land",
    "--modis": "modis_lst",
    "--smap": "smap_moisture",
    "--sentinel1": "sentinel1_sar",
}


def _completed_worker_result(command):
    location_id = command[command.index("--location-id") + 1]
    source = command[command.index("--source") + 1] if "--source" in command else None
    sources = [source] if source else sorted(climate_data._CLIMATE_SOURCE_KEYS)
    results = {
        key: {"status": "success", "record_id": f"record-{key}"}
        for key in sources
    }
    report = {
        "status": "success",
        "location_id": location_id,
        "results": results,
        "success": len(sources),
        "skipped": 0,
        "failed": 0,
        "total": len(sources),
    }
    return SimpleNamespace(stdout=json.dumps(report), returncode=0)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--worldclim"], {"status": "success", "record_id": "record-worldclim"}),
        (["--ncep"], {"status": "success", "record_id": "record-era5_land"}),
        (["--modis"], {"status": "success", "record_id": "record-modis_lst"}),
        (["--smap"], {"status": "success", "record_id": "record-smap_moisture"}),
        (["--sentinel1"], {"status": "success", "record_id": "record-sentinel1_sar"}),
        (["--all"], None),
    ],
)
def test_climate_cli_success_receipts_match_standalone_and_unified(
    monkeypatch, capsys, arguments, expected
):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    calls = []
    monkeypatch.setattr(climate_data, "is_enabled", lambda _feature: True)
    monkeypatch.setattr(
        climate_data.subprocess,
        "run",
        lambda command, **_kwargs: calls.append(list(command)) or _completed_worker_result(command),
    )
    full_arguments = [*arguments, "--location-id", LOCATION_ID]

    assert climate_data.main(full_arguments) == 0
    standalone_output = capsys.readouterr().out
    unified = CliRunner().invoke(
        unified_cli.app, ["ingestion", "--", "climate_data", *full_arguments]
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    if expected is None:
        parsed = json.loads(standalone_output)
        assert parsed["status"] == "success"
        assert parsed["total"] == 5
        assert list(parsed["results"]) == ["worldclim", "ncep", "modis", "smap", "sentinel1"]
    else:
        assert json.loads(standalone_output) == expected
    assert len(calls) == 2
    assert all("-m" in command and "services.ingestion.climate_worker" in command for command in calls)
    assert all(LOCATION_ID in command for command in calls)
    assert unified.stderr == ""


@pytest.mark.parametrize("entrypoint", ["standalone", "unified"])
def test_climate_cli_rejects_multiple_datasets_before_worker(monkeypatch, entrypoint):
    from typer.testing import CliRunner

    import services.cli as unified_cli

    monkeypatch.setattr(
        climate_data.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("conflicting selectors must fail before dispatch"),
    )
    arguments = ["--worldclim", "--modis", "--location-id", LOCATION_ID]

    if entrypoint == "standalone":
        with pytest.raises(SystemExit) as exc_info:
            climate_data.main(arguments)
        assert exc_info.value.code == 2
    else:
        result = CliRunner().invoke(
            unified_cli.app, ["ingestion", "--", "climate_data", *arguments]
        )
        assert result.exit_code == 2
        assert "not allowed with argument" in result.output
