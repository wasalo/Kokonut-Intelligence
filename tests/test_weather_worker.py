"""Signed current-weather worker stays scoped and provider-safe."""

from __future__ import annotations

import json
import sys
import traceback
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.ingestion import weather_worker as worker

LOCATION_ID = str(uuid4())
LOCATION_B = str(uuid4())
RAW_CREDENTIAL = "synthetic-current-weather-worker-credential-over-32-bytes"
PROVIDER_KEY = "synthetic-openweathermap-worker-key"


def _record(location_id: str = LOCATION_ID) -> dict:
    return {
        "location_id": location_id,
        "observation_date": "2026-10-17",
        "observation_time": "12:30:00+00:00",
        "source": "openweathermap",
        "temperature_c": 24.5,
        "humidity_pct": 70,
        "precipitation_mm": 0,
        "wind_speed_kmh": 4.0,
        "wind_direction_deg": 90,
        "pressure_hpa": 1012,
        "visibility_km": 10,
        "cloud_cover_pct": 15,
        "metadata": '{"weather_main":"Clear"}',
    }


def _projection() -> dict:
    return {
        "columns": ["timestamp", "location_id", "source"],
        "rows": [["2026-10-17T12:30:00+00:00", LOCATION_ID, "openweathermap"]],
        "payload_hash": "a" * 64,
    }


def test_invalid_location_fails_before_provider_or_database_configuration():
    with patch.object(worker, "_provider_api_key") as key, \
            patch.object(worker, "get_worker_credential") as credential, \
            patch.object(worker, "get_worker_db") as database:
        with pytest.raises(ValueError):
            worker.ingest("invalid")
    key.assert_not_called()
    credential.assert_not_called()
    database.assert_not_called()


def test_missing_worker_provider_key_fails_before_database_access():
    with patch.dict("os.environ", {"KOKONUT_WEATHER_OPENWEATHERMAP_API_KEY": ""}), \
            patch.object(worker, "get_worker_credential") as credential, \
            patch.object(worker, "get_worker_db") as database:
        with pytest.raises(RuntimeError, match="provider key is not configured"):
            worker._provider_api_key()
    credential.assert_not_called()
    database.assert_not_called()


def test_provider_fetch_uses_exact_worker_key_and_closes_response():
    response = MagicMock()
    response.json.return_value = {"id": 7}
    with patch.object(worker.http, "get", return_value=response) as get:
        assert worker._fetch_weather(18.5, -69.9, PROVIDER_KEY) == {"id": 7}
    assert get.call_args.kwargs["params"]["appid"] == PROVIDER_KEY
    assert get.call_args.kwargs["params"]["lat"] == 18.5
    response.close.assert_called_once_with()


def test_signed_location_lookup_commits_and_closes_short_transaction():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (18.5, -69.9)
    with patch.object(worker, "get_worker_db", return_value=connection) as get_db, \
            patch.object(worker, "set_worker_tenant_context") as set_context:
        assert worker._load_location(LOCATION_ID, RAW_CREDENTIAL) == (18.5, -69.9)

    get_db.assert_called_once_with("weather")
    set_context.assert_called_once_with(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=LOCATION_ID,
        resource="weather_observation",
        action="ingest",
    )
    cursor.execute.assert_called_once_with(
        "SELECT latitude, longitude "
        "FROM kokonut_security.weather_observation_location(%s::uuid)",
        (LOCATION_ID,),
    )
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_missing_signed_location_rolls_back_and_closes():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = None
    with patch.object(worker, "get_worker_db", return_value=connection), \
            patch.object(worker, "set_worker_tenant_context"):
        with pytest.raises(ValueError, match="not active or has no coordinates"):
            worker._load_location(LOCATION_ID, RAW_CREDENTIAL)
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_store_observation_passes_json_object_and_signed_location():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = ("obs-id", True)
    record = _record()
    projection = _projection()
    with patch.object(worker, "get_worker_db", return_value=connection), \
            patch.object(worker, "set_worker_tenant_context") as set_context:
        assert worker._store_observation(
            LOCATION_ID,
            RAW_CREDENTIAL,
            record=record,
            projection=projection,
            provider_source_id="7",
            provider_payload_hash="b" * 64,
            processing_time_ms=15,
        ) == ("obs-id", True)

    set_context.assert_called_once_with(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=LOCATION_ID,
        resource="weather_observation",
        action="ingest",
    )
    statement, parameters = connection.cursor.return_value.__enter__.return_value.execute.call_args.args
    assert "kokonut_security.store_weather_observation" in statement
    assert json.loads(parameters[1])["metadata"] == {"weather_main": "Clear"}
    assert json.loads(parameters[2]) == projection["rows"]
    assert parameters[0] == LOCATION_ID
    assert parameters[3:7] == (
        projection["payload_hash"], "7", "b" * 64, 15,
    )
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_store_failure_records_only_sanitized_error_contract():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (None, False)
    with patch.object(worker, "get_worker_db", return_value=connection), \
            patch.object(worker, "set_worker_tenant_context"):
        assert worker._store_observation(
            LOCATION_ID,
            RAW_CREDENTIAL,
            record=None,
            projection=None,
            provider_source_id="",
            provider_payload_hash=None,
            processing_time_ms=12,
            error_text="weather fetch or parsing failed (RuntimeError)",
        ) == (None, False)
    parameters = connection.cursor.return_value.__enter__.return_value.execute.call_args.args[1]
    assert parameters[1] is None
    assert json.loads(parameters[2]) == []
    assert parameters[7] == "weather fetch or parsing failed (RuntimeError)"
    connection.commit.assert_called_once_with()


def test_successful_ingest_fetches_outside_db_transaction_and_persists_once():
    raw = {"id": 7}
    record = _record()
    projection = _projection()
    with patch.object(worker, "_provider_api_key", return_value=PROVIDER_KEY), \
            patch.object(worker, "get_worker_credential", return_value=RAW_CREDENTIAL), \
            patch.object(worker, "_load_location", return_value=(18.5, -69.9)) as lookup, \
            patch.object(worker, "_fetch_weather", return_value=raw) as fetch, \
            patch.object(worker, "parse_weather", return_value=record) as parse, \
            patch.object(worker, "build_weather_clickhouse_projection", return_value=projection), \
            patch.object(worker, "_store_observation", return_value=("obs-id", True)) as store:
        assert worker.ingest(LOCATION_ID) == ("obs-id", True)

    lookup.assert_called_once_with(LOCATION_ID, RAW_CREDENTIAL)
    fetch.assert_called_once_with(18.5, -69.9, PROVIDER_KEY)
    parse.assert_called_once_with(raw, LOCATION_ID)
    store.assert_called_once()
    assert store.call_args.args[0:2] == (LOCATION_ID, RAW_CREDENTIAL)
    assert store.call_args.kwargs["provider_source_id"] == "7"
    assert store.call_args.kwargs["processing_time_ms"] >= 0


def test_provider_failure_is_audited_without_leaking_key_or_url():
    provider_error = RuntimeError(
        "request failed https://provider.invalid/?appid=" + PROVIDER_KEY
    )
    with patch.object(worker, "_provider_api_key", return_value=PROVIDER_KEY), \
            patch.object(worker, "get_worker_credential", return_value=RAW_CREDENTIAL), \
            patch.object(worker, "_load_location", return_value=(18.5, -69.9)), \
            patch.object(worker, "_fetch_weather", side_effect=provider_error), \
            patch.object(worker, "_store_observation", return_value=(None, False)) as store:
        with pytest.raises(
            RuntimeError,
            match=r"weather fetch or parsing failed \(RuntimeError\)",
        ) as raised:
            worker.ingest(LOCATION_ID)

    assert raised.value is not provider_error
    assert PROVIDER_KEY not in str(raised.value)
    assert store.call_args.kwargs["error_text"] == "weather fetch or parsing failed (RuntimeError)"
    assert PROVIDER_KEY not in store.call_args.kwargs["error_text"]
    assert store.call_args.kwargs["record"] is None
    assert store.call_args.kwargs["provider_payload_hash"] is None


def test_provider_and_failure_audit_errors_are_redacted_from_traceback(caplog):
    provider_url = f"https://provider.invalid/weather?appid={PROVIDER_KEY}"
    provider_error = RuntimeError(f"request failed: {provider_url}")
    audit_error = RuntimeError(f"audit persistence failed for {PROVIDER_KEY}")

    with patch.object(worker, "_provider_api_key", return_value=PROVIDER_KEY), \
            patch.object(worker, "get_worker_credential", return_value=RAW_CREDENTIAL), \
            patch.object(worker, "_load_location", return_value=(18.5, -69.9)), \
            patch.object(worker, "_fetch_weather", side_effect=provider_error), \
            patch.object(worker, "_store_observation", side_effect=audit_error):
        with pytest.raises(RuntimeError, match="weather fetch or parsing failed") as raised:
            worker.ingest(LOCATION_ID)

    formatted = "".join(
        traceback.format_exception(raised.type, raised.value, raised.value.__traceback__)
    )
    assert PROVIDER_KEY not in str(raised.value)
    assert provider_url not in str(raised.value)
    assert PROVIDER_KEY not in formatted
    assert provider_url not in formatted
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert PROVIDER_KEY not in caplog.text
    assert "Weather failure audit could not be persisted (RuntimeError)" in caplog.text


def test_disabled_cli_fails_before_ingestion():
    with patch.object(sys, "argv", ["weather_worker", "--location-id", LOCATION_ID]), \
            patch.object(worker, "is_enabled", return_value=False), \
            patch.object(worker, "ingest") as ingest:
        with pytest.raises(SystemExit) as exc:
            worker.main()
    assert exc.value.code == 2
    ingest.assert_not_called()
