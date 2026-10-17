from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from services.common.worker_environment import (
    scheduled_module_worker_key,
    worker_subprocess_environment,
)
from services.core.jobs import JOBS
from services.ingestion import climate_worker
from services.security.scheduled_command_contracts import (
    ScheduledCommandRejected,
    validate_scheduled_command,
)

LOCATION_ID = "11111111-1111-4111-8111-111111111111"


def test_climate_worker_secrets_are_forwarded_only_to_exact_module():
    source = {
        "PATH": "/usr/bin",
        "PG_PASSWORD": "shared-db-secret",
        "KOKONUT_CLIMATE_DATABASE_URL": "postgresql://climate-only",
        "KOKONUT_CLIMATE_WORKER_CREDENTIAL": "climate-credential",
        "KOKONUT_CLIMATE_GEE_SERVICE_ACCOUNT_KEY": "/run/secrets/climate.json",
        "KOKONUT_WEATHER_DATABASE_URL": "postgresql://weather-only",
    }

    assert scheduled_module_worker_key("services.ingestion.climate_worker") == "climate"
    assert scheduled_module_worker_key("services.ingestion.climate_data") is None
    climate_env = worker_subprocess_environment(
        allowed_worker_keys=("climate",),
        isolated_database_credentials=True,
        environ=source,
    )
    assert climate_env["KOKONUT_CLIMATE_DATABASE_URL"] == "postgresql://climate-only"
    assert climate_env["KOKONUT_CLIMATE_WORKER_CREDENTIAL"] == "climate-credential"
    assert climate_env["KOKONUT_CLIMATE_GEE_SERVICE_ACCOUNT_KEY"] == "/run/secrets/climate.json"
    assert "KOKONUT_WEATHER_DATABASE_URL" not in climate_env
    assert "PG_PASSWORD" not in climate_env
    weather_env = worker_subprocess_environment(
        allowed_worker_keys=("weather",),
        isolated_database_credentials=True,
        environ=source,
    )
    assert weather_env["KOKONUT_WEATHER_DATABASE_URL"] == "postgresql://weather-only"
    assert not any(key.startswith("KOKONUT_CLIMATE_") for key in weather_env)


def test_climate_jobs_require_one_location_and_use_signed_worker():
    job = JOBS["climate"]
    assert job.module == "services.ingestion.climate_worker"
    assert job.arguments == ()
    assert job.required_inputs == ("location_id",)

    validate_scheduled_command(job.module, ["--location-id", LOCATION_ID])
    with pytest.raises(ScheduledCommandRejected, match="one explicit location"):
        validate_scheduled_command(job.module, [])
    with pytest.raises(ScheduledCommandRejected, match="unsupported option"):
        validate_scheduled_command(job.module, ["--location-id", LOCATION_ID, "--all"])


def test_worldclim_worker_payload_is_explicitly_a_latitude_proxy():
    summary = climate_worker._worldclim_summary(18.5, -69.9)

    assert summary["source_key"] == "worldclim"
    assert summary["resolution_m"] is None
    assert summary["target_date"] is None
    assert summary["metadata"]["estimation_method"] == "latitude_proxy_v1"
    assert len(summary["metadata"]["estimated_bioclimatic_variables"]) == 19
    assert summary["values"]["bio1_mean_annual_temp"] == 12.05


def test_ingest_routes_all_five_sources_through_signed_storage(monkeypatch):
    stores: list[tuple[str, dict | None, str | None]] = []
    monkeypatch.setattr(climate_worker, "get_worker_credential", lambda _key: "credential")
    monkeypatch.setattr(
        climate_worker,
        "_load_location",
        lambda _location_id, _credential: {
            "latitude": 18.5,
            "longitude": -69.9,
            "bbox": {"west": -70, "south": 18, "east": -69, "north": 19},
        },
    )

    def store(_location_id, _credential, *, source_key, summary, processing_time_ms, error_text=None):
        stores.append((source_key, summary, error_text))
        return f"record-{source_key}" if summary is not None else None

    monkeypatch.setattr(climate_worker, "_store_result", store)

    def fetcher_for(source_key):
        def fetch(connection, location_id, bbox, **kwargs):
            assert connection is None
            assert location_id == LOCATION_ID
            assert bbox["west"] == -70
            source_summary = {
                "source_key": source_key,
                "target_date": "2026-10-17",
                "resolution_m": 10,
                "values": {"synthetic": 1},
                "metadata": {},
            }
            record_id = kwargs["persist_summary"](source_summary)
            return {"status": "success", "record_id": record_id}

        return fetch

    sources = ("era5_land", "modis_lst", "smap_moisture", "sentinel1_sar")
    monkeypatch.setattr(
        climate_worker,
        "_PROVIDERS",
        tuple((name, fetcher_for(name)) for name in sources),
    )

    report = climate_worker.ingest(LOCATION_ID)

    assert report["status"] == "success"
    assert report["total"] == 5
    assert {source for source, _summary, error in stores if error is None} == {
        "worldclim", *sources,
    }
    assert all(summary is not None for _source, summary, error in stores if error is None)


def test_provider_failures_are_sanitized_and_return_retryable_error(monkeypatch):
    stores: list[tuple[str, dict | None, str | None]] = []
    monkeypatch.setattr(climate_worker, "get_worker_credential", lambda _key: "credential")
    monkeypatch.setattr(
        climate_worker,
        "_load_location",
        lambda _location_id, _credential: {
            "latitude": 18.5,
            "longitude": -69.9,
            "bbox": {"west": -70, "south": 18, "east": -69, "north": 19},
        },
    )
    monkeypatch.setattr(
        climate_worker,
        "_store_result",
        lambda _location_id, _credential, *, source_key, summary, processing_time_ms, error_text=None: (
            stores.append((source_key, summary, error_text)) or None
        ),
    )

    def unavailable(*_args, **_kwargs):
        return {"status": "error", "message": "provider URL contained a secret"}

    monkeypatch.setattr(climate_worker, "_PROVIDERS", (("era5_land", unavailable),))
    report = climate_worker.ingest(LOCATION_ID)

    assert report["status"] == "error"
    assert report["failed"] == 1
    failure = next(entry for entry in stores if entry[0] == "era5_land")
    assert failure == ("era5_land", None, "climate provider fetch failed")
    assert "secret" not in str(report)


def test_worker_fails_closed_when_feature_is_disabled(monkeypatch):
    monkeypatch.setattr(climate_worker, "is_enabled", lambda feature: feature == "other")
    monkeypatch.setattr("sys.argv", ["climate_worker", "--location-id", LOCATION_ID])

    with pytest.raises(SystemExit) as raised:
        climate_worker.main()
    assert raised.value.code == 2


def test_feature_definition_defaults_to_disabled():
    from services.core import features

    assert features.FEATURES["signed_climate_worker"]["enabled"] is False
    assert features.get_feature("signed_climate_worker")["category"] == "security"


def test_signed_gee_client_ignores_shared_legacy_key_path(monkeypatch, tmp_path):
    from services.ingestion import gee_climate

    legacy_key = tmp_path / "legacy.json"
    legacy_key.write_text("synthetic legacy key", encoding="utf-8")
    calls = []
    fake_ee = SimpleNamespace(
        ServiceAccountCredentials=lambda *args: calls.append(("credentials", args)),
        Initialize=lambda *args: calls.append(("initialize", args)),
    )
    monkeypatch.setitem(sys.modules, "ee", fake_ee)
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_KEY", str(legacy_key))
    monkeypatch.delenv("KOKONUT_CLIMATE_GEE_SERVICE_ACCOUNT_KEY", raising=False)

    assert gee_climate._get_gee_client(worker_credentials=True) is None
    assert calls == []


def test_signed_gee_client_uses_only_scoped_service_account_path(monkeypatch, tmp_path):
    from services.ingestion import gee_climate

    scoped_key = tmp_path / "climate.json"
    scoped_key.write_text("synthetic climate key", encoding="utf-8")
    legacy_key = tmp_path / "legacy.json"
    legacy_key.write_text("synthetic legacy key", encoding="utf-8")
    calls = []
    fake_credentials = object()
    fake_ee = SimpleNamespace(
        ServiceAccountCredentials=lambda *args: (calls.append(("credentials", args)) or fake_credentials),
        Initialize=lambda *args: calls.append(("initialize", args)),
    )
    monkeypatch.setitem(sys.modules, "ee", fake_ee)
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_KEY", str(legacy_key))
    monkeypatch.setenv("KOKONUT_CLIMATE_GEE_SERVICE_ACCOUNT_KEY", str(scoped_key))

    assert gee_climate._get_gee_client(worker_credentials=True) is fake_ee
    assert calls == [
        ("credentials", (None, str(scoped_key))),
        ("initialize", (fake_credentials,)),
    ]
