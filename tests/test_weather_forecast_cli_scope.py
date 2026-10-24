"""Manual weather forecast ingestion requires an explicit location scope."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from services.ingestion import weather_forecast

LOCATION_ID = "5e15b529-965d-4845-9c76-2f80fb781a8f"


class EmptyLocationConnection:
    def __init__(self):
        self.cursor_context = MagicMock()
        self.cursor_obj = MagicMock()
        self.cursor_obj.fetchall.return_value = []
        self.cursor_context.__enter__.return_value = self.cursor_obj
        self.cursor_context.__exit__.return_value = False
        self.closed = False

    def cursor(self):
        return self.cursor_context

    def close(self):
        self.closed = True


def test_no_scope_prints_offline_help(capsys):
    with patch.object(weather_forecast, "run") as run:
        weather_forecast.main([])

    output = capsys.readouterr().out
    assert "--location-id" in output
    assert "--all-locations" in output
    run.assert_not_called()


def test_missing_scope_fails_before_key_or_database_access():
    with (
        patch.object(weather_forecast, "OPENWEATHERMAP_API_KEY", ""),
        patch.object(weather_forecast, "get_db") as get_db,
        pytest.raises(ValueError, match="provide --location-id"),
    ):
        weather_forecast.run()

    get_db.assert_not_called()


def test_invalid_location_fails_before_database_access():
    with patch.object(weather_forecast, "get_db") as get_db, pytest.raises(SystemExit) as exc:
        weather_forecast.main(["--location-id", "not-a-uuid"])

    assert exc.value.code == 2
    get_db.assert_not_called()


def test_single_location_query_is_canonical_and_requires_coordinates():
    db = EmptyLocationConnection()
    uppercase_location = str(UUID(LOCATION_ID)).upper()
    with (
        patch.object(weather_forecast, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather_forecast, "get_db", return_value=db),
        patch.object(weather_forecast, "fetch_forecast_raw") as fetch_forecast,
    ):
        weather_forecast.run(location_id=uppercase_location)

    sql, params = db.cursor_obj.execute.call_args.args
    assert "WHERE id = %s" in sql
    assert "status = 'active'" in sql
    assert "center IS NOT NULL" in sql
    assert params == (LOCATION_ID,)
    fetch_forecast.assert_not_called()
    assert db.closed


def test_aggregate_query_runs_only_after_explicit_selection():
    db = EmptyLocationConnection()
    with (
        patch.object(weather_forecast, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather_forecast, "get_db", return_value=db),
        patch.object(weather_forecast, "fetch_forecast_raw") as fetch_forecast,
    ):
        weather_forecast.run(all_locations=True)

    (sql,), params = db.cursor_obj.execute.call_args.args, db.cursor_obj.execute.call_args.kwargs
    assert "WHERE status = 'active'" in sql
    assert "center IS NOT NULL" in sql
    assert params == {}
    fetch_forecast.assert_not_called()
    assert db.closed


def test_cli_forwards_single_and_aggregate_modes():
    with patch.object(weather_forecast, "run") as run:
        weather_forecast.main(["--location-id", LOCATION_ID])
        run.assert_called_once_with(location_id=LOCATION_ID, all_locations=False)

    with patch.object(weather_forecast, "run") as run:
        weather_forecast.main(["--all-locations"])
        run.assert_called_once_with(location_id=None, all_locations=True)


@pytest.mark.parametrize(
    "query",
    [weather_forecast.get_daily_summary, weather_forecast.get_spray_windows],
)
def test_forecast_read_helpers_reject_invalid_scope_before_query(query):
    db = MagicMock()

    with pytest.raises(ValueError, match="location_id must be a UUID"):
        query(db, "not-a-uuid")

    db.cursor.assert_not_called()


@pytest.mark.parametrize(
    ("query", "view"),
    [
        (weather_forecast.get_daily_summary, "v_weather_forecast_daily"),
        (weather_forecast.get_spray_windows, "v_spray_window"),
    ],
)
def test_forecast_read_helpers_bind_canonical_location_scope(query, view):
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.description = [("forecast_date",)]
    cursor.fetchall.return_value = []

    query(db, str(UUID(LOCATION_ID)).upper())

    sql, params = cursor.execute.call_args.args
    assert f"FROM {view}" in sql
    assert "WHERE location_id = %s" in sql
    assert params == (LOCATION_ID, 5)
