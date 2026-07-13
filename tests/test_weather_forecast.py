"""Tests for Weather Forecast module."""

import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock

import pytest


# ============================================================
# parse_forecast_list
# ============================================================

class TestParseForecastList:
    """Test parsing of OpenWeatherMap forecast API response."""

    def _sample_response(self):
        return {
            "list": [
                {
                    "dt": 1700000000,
                    "main": {
                        "temp": 22.5,
                        "temp_min": 19.0,
                        "temp_max": 25.0,
                        "feels_like": 21.8,
                        "humidity": 68,
                        "pressure": 1013,
                    },
                    "wind": {"speed": 3.5, "deg": 180, "gust": 5.2},
                    "rain": {"3h": 2.5},
                    "clouds": {"all": 45},
                    "visibility": 10000,
                    "pop": 0.6,
                    "weather": [{"main": "Rain", "description": "light rain", "id": 500}],
                    "dt_txt": "2023-11-14 12:00:00",
                    "uv": 4.2,
                },
                {
                    "dt": 1700010800,
                    "main": {
                        "temp": 18.0,
                        "temp_min": 16.0,
                        "temp_max": 20.0,
                        "feels_like": 17.5,
                        "humidity": 75,
                        "pressure": 1012,
                    },
                    "wind": {"speed": 2.0, "deg": 200},
                    "rain": {},
                    "clouds": {"all": 80},
                    "visibility": 8000,
                    "pop": 0.2,
                    "weather": [{"main": "Clouds", "description": "overcast", "id": 804}],
                    "dt_txt": "2023-11-14 15:00:00",
                },
            ]
        }

    def test_parses_forecast_list(self):
        from services.ingestion.weather_forecast import parse_forecast_list

        data = self._sample_response()
        loc_id = str(uuid.uuid4())
        records = parse_forecast_list(data, loc_id)

        assert len(records) == 2
        assert records[0]["location_id"] == loc_id
        assert records[0]["source"] == "openweathermap"

    def test_extracts_temperature(self):
        from services.ingestion.weather_forecast import parse_forecast_list

        records = parse_forecast_list(self._sample_response(), str(uuid.uuid4()))
        r = records[0]

        assert r["temp_c"] == 22.5
        assert r["temp_min_c"] == 19.0
        assert r["temp_max_c"] == 25.0
        assert r["feels_like_c"] == 21.8

    def test_extracts_precipitation(self):
        from services.ingestion.weather_forecast import parse_forecast_list

        records = parse_forecast_list(self._sample_response(), str(uuid.uuid4()))
        r = records[0]

        assert r["precipitation_mm"] == 2.5
        assert r["rain_3h_mm"] == 2.5
        assert r["precipitation_prob_pct"] == 60.0

    def test_extracts_wind(self):
        from services.ingestion.weather_forecast import parse_forecast_list

        records = parse_forecast_list(self._sample_response(), str(uuid.uuid4()))
        r = records[0]

        assert r["wind_speed_kmh"] == pytest.approx(3.5 * 3.6, 0.1)
        assert r["wind_gust_kmh"] == pytest.approx(5.2 * 3.6, 0.1)
        assert r["wind_direction_deg"] == 180

    def test_empty_list(self):
        from services.ingestion.weather_forecast import parse_forecast_list

        records = parse_forecast_list({"list": []}, str(uuid.uuid4()))
        assert records == []

    def test_missing_fields_handled(self):
        from services.ingestion.weather_forecast import parse_forecast_list

        data = {"list": [{"dt": 1700000000}]}
        records = parse_forecast_list(data, str(uuid.uuid4()))
        assert len(records) == 1
        assert records[0]["temp_c"] is None

    def test_forecast_date_and_hour(self):
        from services.ingestion.weather_forecast import parse_forecast_list

        records = parse_forecast_list(self._sample_response(), str(uuid.uuid4()))
        r = records[0]

        assert "forecast_date" in r
        assert "forecast_hour" in r
        assert isinstance(r["forecast_date"], str)
        assert isinstance(r["forecast_hour"], int)

    def test_metadata_includes_weather_main(self):
        from services.ingestion.weather_forecast import parse_forecast_list

        records = parse_forecast_list(self._sample_response(), str(uuid.uuid4()))
        meta = json.loads(records[0]["metadata"])

        assert meta["weather_main"] == "Rain"
        assert meta["dt_txt"] is not None


# ============================================================
# get_daily_summary (mock DB)
# ============================================================

class TestGetDailySummary:
    """Test daily forecast summary query."""

    def test_returns_formatted_summary(self):
        from services.ingestion.weather_forecast import get_daily_summary

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchall.return_value = [
            (date(2026, 1, 15), 16.0, 24.0, 20.0, 5.0, 60.0, 65.0, 12.0, 6.0),
        ]
        mock_cursor.description = [
            ("forecast_date",), ("temp_min_c",), ("temp_max_c",),
            ("temp_avg_c",), ("precipitation_total_mm",),
            ("max_precip_prob_pct",), ("avg_humidity_pct",),
            ("avg_wind_speed_kmh",), ("max_uv_index",),
        ]

        result = get_daily_summary(mock_conn, str(uuid.uuid4()))

        assert len(result) == 1
        assert result[0]["temp_min_c"] == 16.0
        assert result[0]["precipitation_total_mm"] == 5.0


# ============================================================
# get_spray_windows (mock DB)
# ============================================================

class TestGetSprayWindows:
    """Test spray window query."""

    def test_returns_suitability(self):
        from services.ingestion.weather_forecast import get_spray_windows

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchall.return_value = [
            (date(2026, 1, 15), 8.0, 20.0, 22.0, "suitable"),
            (date(2026, 1, 16), 18.0, 60.0, 25.0, "unsuitable"),
        ]
        mock_cursor.description = [
            ("forecast_date",), ("avg_wind_speed_kmh",),
            ("max_precip_prob_pct",), ("temp_avg_c",),
            ("spray_suitability",),
        ]

        result = get_spray_windows(mock_conn, str(uuid.uuid4()))

        assert len(result) == 2
        assert result[0]["spray_suitability"] == "suitable"
        assert result[1]["spray_suitability"] == "unsuitable"


# ============================================================
# insert_forecasts (mock DB)
# ============================================================

class TestInsertForecasts:
    """Test forecast insertion with upsert."""

    def test_inserts_records(self):
        from services.ingestion.weather_forecast import insert_forecasts

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        records = [
            {
                "location_id": str(uuid.uuid4()),
                "source": "openweathermap",
                "forecast_date": "2026-01-15",
                "forecast_hour": 12,
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
            },
        ]

        count = insert_forecasts(mock_conn, records)
        assert count == 1
        assert mock_cursor.execute.call_count == 1

    def test_empty_records(self):
        from services.ingestion.weather_forecast import insert_forecasts

        mock_conn = MagicMock()
        count = insert_forecasts(mock_conn, [])
        assert count == 0
