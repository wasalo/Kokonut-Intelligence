"""Signed weather-worker boundaries use mocks and never contact providers/DBs."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.ingestion import weather_forecast_worker as worker

LOCATION_ID = str(uuid4())
RAW_CREDENTIAL = "synthetic-weather-worker-credential-with-more-than-32-bytes"


def _record() -> dict:
    return {
        "location_id": LOCATION_ID,
        "source": "openweathermap",
        "forecast_date": "2026-10-16",
        "forecast_hour": 12,
        "temp_c": 24.0,
        "temp_min_c": 20.0,
        "temp_max_c": 27.0,
        "feels_like_c": 25.0,
        "humidity_pct": 70,
        "precipitation_mm": 0,
        "precipitation_prob_pct": 0,
        "rain_3h_mm": 0,
        "wind_speed_kmh": 4.0,
        "wind_direction_deg": 90,
        "wind_gust_kmh": 6.0,
        "cloud_cover_pct": 10,
        "visibility_km": 10,
        "pressure_hpa": 1012,
        "uv_index": 4,
        "description": "clear sky",
        "metadata": '{"weather_main":"Clear"}',
    }


def test_invalid_location_fails_before_loading_credentials_or_database():
    with patch.object(worker, "get_worker_credential") as credential:
        with pytest.raises(ValueError):
            worker.ingest("not-a-uuid")
    credential.assert_not_called()


def test_missing_provider_key_fails_before_worker_database_access():
    with patch.object(worker, "OPENWEATHERMAP_API_KEY", ""), \
            patch.object(worker, "get_worker_credential") as credential, \
            patch.object(worker, "get_worker_db") as database:
        with pytest.raises(RuntimeError, match="API key is not configured"):
            worker.ingest(LOCATION_ID)
    credential.assert_not_called()
    database.assert_not_called()


def test_signed_location_lookup_commits_and_closes_its_short_transaction():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("Kokonut Adelphi", 18.5, -69.9)
    with patch.object(worker, "get_worker_db", return_value=connection) as get_db, \
            patch.object(worker, "set_worker_tenant_context") as set_context:
        result = worker._load_location(LOCATION_ID, RAW_CREDENTIAL)

    assert result == ("Kokonut Adelphi", 18.5, -69.9)
    get_db.assert_called_once_with("weather_forecast")
    set_context.assert_called_once_with(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=LOCATION_ID,
        resource="weather_forecast",
        action="ingest",
    )
    cursor.execute.assert_called_once_with(
        "SELECT location_name, latitude, longitude "
        "FROM kokonut_security.weather_forecast_location(%s::uuid)",
        (LOCATION_ID,),
    )
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_missing_signed_location_rolls_back_and_closes():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    with patch.object(worker, "get_worker_db", return_value=connection), \
            patch.object(worker, "set_worker_tenant_context"):
        with pytest.raises(ValueError, match="not active or has no coordinates"):
            worker._load_location(LOCATION_ID, RAW_CREDENTIAL)
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_store_batch_passes_json_object_metadata_and_signed_location():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (1,)
    record = _record()
    projection = {
        "columns": ["timestamp", "location_id"],
        "rows": [["2026-10-16T12:00:00+00:00", LOCATION_ID]],
        "payload_hash": "a" * 64,
    }
    with patch.object(worker, "get_worker_db", return_value=connection), \
            patch.object(worker, "set_worker_tenant_context") as set_context:
        assert worker._store_batch(
            LOCATION_ID,
            RAW_CREDENTIAL,
            records=[record],
            projection=projection,
            provider_source_id="provider-city-7",
            provider_payload_hash="b" * 64,
            processing_time_ms=24,
        ) == 1

    set_context.assert_called_once_with(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=LOCATION_ID,
        resource="weather_forecast",
        action="ingest",
    )
    statement, parameters = cursor.execute.call_args.args
    assert "kokonut_security.store_weather_forecast_batch" in statement
    forecast_rows = json.loads(parameters[1])
    assert forecast_rows[0]["metadata"] == {"weather_main": "Clear"}
    assert parameters[0] == LOCATION_ID
    assert parameters[2] == json.dumps(projection["rows"])
    assert parameters[3:7] == (
        projection["payload_hash"],
        "provider-city-7",
        "b" * 64,
        24,
    )
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_successful_ingest_revalidates_scope_after_provider_fetch():
    raw = {"city": {"id": 7}, "list": []}
    records = [_record()]
    projection = {"columns": [], "rows": [], "payload_hash": "c" * 64}
    with patch.object(worker, "OPENWEATHERMAP_API_KEY", "synthetic-key"), \
            patch.object(worker, "get_worker_credential", return_value=RAW_CREDENTIAL), \
            patch.object(worker, "_load_location", return_value=("Adelphi", 18.5, -69.9)) as lookup, \
            patch.object(worker, "fetch_forecast_raw", return_value=raw), \
            patch.object(worker, "parse_forecast_list", return_value=records), \
            patch.object(worker, "build_forecast_clickhouse_projection", return_value=projection), \
            patch.object(worker, "_store_batch", return_value=1) as store:
        assert worker.ingest(LOCATION_ID) == 1

    lookup.assert_called_once_with(LOCATION_ID, RAW_CREDENTIAL)
    store.assert_called_once()
    assert store.call_args.args[:2] == (LOCATION_ID, RAW_CREDENTIAL)
    assert store.call_args.kwargs["records"] == records
    assert store.call_args.kwargs["provider_source_id"] == "7"
    assert store.call_args.kwargs["processing_time_ms"] >= 0


def test_provider_error_is_audited_without_persisting_exception_text():
    provider_error = RuntimeError(
        "request failed https://provider.invalid/?appid=synthetic-secret"
    )
    with patch.object(worker, "OPENWEATHERMAP_API_KEY", "synthetic-key"), \
            patch.object(worker, "get_worker_credential", return_value=RAW_CREDENTIAL), \
            patch.object(worker, "_load_location", return_value=("Adelphi", 18.5, -69.9)), \
            patch.object(worker, "fetch_forecast_raw", side_effect=provider_error), \
            patch.object(worker, "_store_batch", return_value=0) as store:
        with pytest.raises(RuntimeError) as raised:
            worker.ingest(LOCATION_ID)

    assert raised.value is provider_error
    error_text = store.call_args.kwargs["error_text"]
    assert error_text == "forecast fetch or parsing failed (RuntimeError)"
    assert "synthetic-secret" not in error_text
    assert store.call_args.kwargs["records"] == []
    assert store.call_args.kwargs["provider_payload_hash"] is None


def test_disabled_cli_fails_before_ingestion():
    with patch.object(sys, "argv", ["weather_forecast_worker", "--location-id", LOCATION_ID]), \
            patch.object(worker, "is_enabled", return_value=False), \
            patch.object(worker, "ingest") as ingest:
        with pytest.raises(SystemExit) as exc:
            worker.main()
    assert exc.value.code == 2
    ingest.assert_not_called()
