"""Forecast persistence and ClickHouse projection share one DB transaction."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import weather_forecast

LOCATION_ID = "5e15b529-965d-4845-9c76-2f80fb781a8f"


def _forecast_record(hour: int = 12) -> dict:
    return {
        "location_id": LOCATION_ID,
        "source": "openweathermap",
        "forecast_date": "2026-10-16",
        "forecast_hour": hour,
        "temp_c": 22.5,
        "temp_min_c": 19.0,
        "temp_max_c": 25.0,
        "feels_like_c": 21.8,
        "humidity_pct": 68,
        "precipitation_mm": 0,
        "precipitation_prob_pct": 10,
        "rain_3h_mm": 0,
        "wind_speed_kmh": 10,
        "wind_direction_deg": 180,
        "wind_gust_kmh": 15,
        "cloud_cover_pct": 45,
        "visibility_km": 10,
        "pressure_hpa": 1013,
        "uv_index": 5,
        "description": "clear",
        "metadata": "{}",
    }


class _CursorContext:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def __enter__(self):
        return self.cursor_obj

    def __exit__(self, *_args):
        return False


class _Connection:
    def __init__(self, location_rows=()):
        self.cursor_obj = MagicMock()
        self.cursor_obj.fetchall.return_value = list(location_rows)
        self.commits = 0
        self.closed = False

    def cursor(self):
        return _CursorContext(self.cursor_obj)

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def test_forecast_insert_errors_propagate_to_location_transaction():
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = RuntimeError("synthetic insert failure")

    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        weather_forecast.insert_forecasts(db, [_forecast_record()])


def test_location_insert_rolls_back_savepoint_after_any_row_fails():
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = [None, RuntimeError("synthetic insert failure"), None, None]

    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        weather_forecast.insert_location_forecasts(
            db, [_forecast_record(12), _forecast_record(15)]
        )

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SAVEPOINT weather_forecast_location",
        statements[1],
        "ROLLBACK TO SAVEPOINT weather_forecast_location",
        "RELEASE SAVEPOINT weather_forecast_location",
    ]
    assert "INSERT INTO weather_forecast" in statements[1]


def test_failed_location_is_not_projected_and_failure_audit_shares_transaction():
    db = _Connection([(LOCATION_ID, "Kokonut Farm", 18.5, -69.9)])
    with (
        patch.object(weather_forecast, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather_forecast, "get_db", return_value=db),
        patch.object(weather_forecast, "fetch_forecast_raw", return_value={"city": {"id": 7}}),
        patch.object(weather_forecast, "parse_forecast_list", return_value=[_forecast_record()]),
        patch.object(
            weather_forecast,
            "insert_location_forecasts",
            side_effect=RuntimeError("synthetic insert failure"),
        ),
        patch.object(weather_forecast, "log_ingestion") as log_ingestion,
        patch.object(weather_forecast, "insert_forecasts_clickhouse") as project,
        patch.object(weather_forecast.time, "sleep"),
    ):
        weather_forecast.run(location_id=LOCATION_ID)

    log_ingestion.assert_called_once()
    assert log_ingestion.call_args.kwargs["status"] == "failed"
    assert log_ingestion.call_args.kwargs["db"] is db
    assert log_ingestion.call_args.kwargs["location_id"] == LOCATION_ID
    project.assert_not_called()
    assert db.commits == 1
    assert db.closed


def test_successful_location_projects_only_after_atomic_insert_and_audits_in_transaction():
    db = _Connection([(LOCATION_ID, "Kokonut Farm", 18.5, -69.9)])
    records = [_forecast_record(12), _forecast_record(15)]
    with (
        patch.object(weather_forecast, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather_forecast, "get_db", return_value=db),
        patch.object(weather_forecast, "fetch_forecast_raw", return_value={"city": {"id": 7}}),
        patch.object(weather_forecast, "parse_forecast_list", return_value=records),
        patch.object(weather_forecast, "insert_location_forecasts", return_value=2) as insert,
        patch.object(weather_forecast, "log_ingestion") as log_ingestion,
        patch.object(weather_forecast, "insert_forecasts_clickhouse") as project,
        patch.object(weather_forecast.time, "sleep"),
    ):
        weather_forecast.run(location_id=LOCATION_ID)

    insert.assert_called_once_with(db, records, source_raw={"city": {"id": 7}})
    log_ingestion.assert_called_once()
    assert log_ingestion.call_args.kwargs["status"] == "success"
    assert log_ingestion.call_args.kwargs["db"] is db
    assert log_ingestion.call_args.kwargs["location_id"] == LOCATION_ID
    project.assert_called_once_with(records, db)
    assert db.commits == 1
    assert db.closed


def test_transactional_clickhouse_enqueue_failure_propagates():
    with patch.object(
        weather_forecast,
        "enqueue",
        side_effect=RuntimeError("synthetic outbox failure"),
    ) as enqueue:
        with pytest.raises(RuntimeError, match="synthetic outbox failure"):
            weather_forecast.insert_forecasts_clickhouse([_forecast_record()], MagicMock())

    enqueue.assert_called_once()


def test_outbox_failure_closes_without_committing_source_transaction():
    db = _Connection([(LOCATION_ID, "Kokonut Farm", 18.5, -69.9)])
    records = [_forecast_record()]
    with (
        patch.object(weather_forecast, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather_forecast, "get_db", return_value=db),
        patch.object(weather_forecast, "fetch_forecast_raw", return_value={"city": {"id": 7}}),
        patch.object(weather_forecast, "parse_forecast_list", return_value=records),
        patch.object(weather_forecast, "insert_location_forecasts", return_value=1),
        patch.object(
            weather_forecast,
            "insert_forecasts_clickhouse",
            side_effect=RuntimeError("synthetic outbox failure"),
        ),
        patch.object(weather_forecast, "log_ingestion"),
        patch.object(weather_forecast.time, "sleep"),
    ):
        with pytest.raises(RuntimeError, match="synthetic outbox failure"):
            weather_forecast.run(location_id=LOCATION_ID)

    assert db.commits == 0
    assert db.closed
