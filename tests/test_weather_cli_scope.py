"""Manual weather ingestion requires an explicit and bounded location scope."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from services.ingestion import weather

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
    with patch.object(weather, "run") as run:
        weather.main([])

    output = capsys.readouterr().out
    assert "--location-id" in output
    assert "--all-locations" in output
    run.assert_not_called()


def test_missing_scope_fails_before_key_or_database_access():
    with (
        patch.object(weather, "OPENWEATHERMAP_API_KEY", ""),
        patch.object(weather, "get_db") as get_db,
        pytest.raises(ValueError, match="provide --location-id"),
    ):
        weather.run()

    get_db.assert_not_called()


def test_invalid_location_cli_input_fails_before_database_access():
    with patch.object(weather, "get_db") as get_db, pytest.raises(SystemExit) as exc:
        weather.main(["--location-id", "not-a-uuid"])

    assert exc.value.code == 2
    get_db.assert_not_called()


def test_location_query_is_scoped_and_requires_coordinates():
    db = EmptyLocationConnection()
    uppercase_location = str(UUID(LOCATION_ID)).upper()
    with (
        patch.object(weather, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather, "get_db", return_value=db),
        patch.object(weather, "fetch_weather") as fetch_weather,
    ):
        weather.run(location_id=uppercase_location)

    sql, params = db.cursor_obj.execute.call_args.args
    assert "WHERE id = %s" in sql
    assert "status = 'active'" in sql
    assert "center IS NOT NULL" in sql
    assert params == (LOCATION_ID,)
    fetch_weather.assert_not_called()
    assert db.closed


def test_all_locations_query_requires_explicit_aggregate_mode():
    db = EmptyLocationConnection()
    with (
        patch.object(weather, "OPENWEATHERMAP_API_KEY", "synthetic-key"),
        patch.object(weather, "get_db", return_value=db),
        patch.object(weather, "fetch_weather") as fetch_weather,
    ):
        weather.run(all_locations=True)

    (sql,), params = db.cursor_obj.execute.call_args.args, db.cursor_obj.execute.call_args.kwargs
    assert "WHERE status = 'active'" in sql
    assert "center IS NOT NULL" in sql
    assert params == {}
    fetch_weather.assert_not_called()
    assert db.closed


def test_cli_forwards_explicit_single_or_aggregate_scope():
    with patch.object(weather, "run") as run:
        weather.main(["--location-id", LOCATION_ID])
        run.assert_called_once_with(location_id=LOCATION_ID, all_locations=False)

    with patch.object(weather, "run") as run:
        weather.main(["--all-locations"])
        run.assert_called_once_with(location_id=None, all_locations=True)
