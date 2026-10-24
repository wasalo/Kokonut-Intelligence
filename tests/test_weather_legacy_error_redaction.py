"""Legacy weather runners must not persist provider or database exception text."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import weather, weather_forecast

LOCATION_ID = "5e15b529-965d-4845-9c76-2f80fb781a8f"
SECRET = "weather-provider-secret"


@pytest.mark.parametrize(
    ("module", "fetch_name", "expected_error"),
    [
        (
            weather,
            "fetch_weather",
            "weather location processing failed (RuntimeError)",
        ),
        (
            weather_forecast,
            "fetch_forecast_raw",
            "forecast location processing failed (RuntimeError)",
        ),
    ],
)
def test_location_failures_hide_exception_text_from_audit_and_logs(module, fetch_name, expected_error):
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(LOCATION_ID, "Test Farm", 18.5, -69.9)]
    logger = MagicMock()

    with (
        patch.object(module, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(module, "get_db", return_value=db),
        patch.object(
            module,
            fetch_name,
            side_effect=RuntimeError(f"request URL included token={SECRET}"),
        ),
        patch.object(module, "log_ingestion") as audit,
        patch.object(module, "logger", logger),
    ):
        module.run(location_id=LOCATION_ID)

    audit.assert_called_once()
    assert audit.call_args.kwargs["status"] == "failed"
    assert audit.call_args.kwargs["error_message"] == expected_error
    assert SECRET not in str(audit.call_args)
    assert SECRET not in str(logger.error.call_args_list)
    db.commit.assert_called_once_with()
    db.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("module", "insert_name", "projection_name"),
    [
        (weather, "insert_weather_clickhouse", "build_weather_clickhouse_projection"),
        (
            weather_forecast,
            "insert_forecasts_clickhouse",
            "build_forecast_clickhouse_projection",
        ),
    ],
)
def test_demo_clickhouse_fallback_hides_exception_text(module, insert_name, projection_name):
    logger = MagicMock()
    projection = {"columns": ["id"], "rows": [["row"]], "payload_hash": "hash"}

    with (
        patch.object(module, projection_name, return_value=projection),
        patch.object(
            module,
            "insert_clickhouse_rows",
            side_effect=RuntimeError(f"ClickHouse URL included token={SECRET}"),
        ),
        patch.object(module, "logger", logger),
    ):
        getattr(module, insert_name)([{}])

    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)
