"""Tests for Crop Phenology module."""

import json
import math
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest


# ============================================================
# GDD Computation
# ============================================================

class TestComputeGDD:
    """Test Growing Degree Day computation."""

    def test_basic_gdd(self):
        from services.analytics.crop_phenology import compute_gdd

        # max=25, min=15, base=10, upper=30 → GDD = min(25,30) - max(15,10) = 25-15 = 10
        gdd = compute_gdd(25, 15, base_temp=10.0, upper_temp=30.0)
        assert gdd == 10.0

    def test_gdd_capped_at_upper(self):
        from services.analytics.crop_phenology import compute_gdd

        # max=35, min=20, base=10, upper=30 → GDD = min(35,30) - max(20,10) = 30-20 = 10
        gdd = compute_gdd(35, 20, base_temp=10.0, upper_temp=30.0)
        assert gdd == 10.0

    def test_gdd_zero_when_below_base(self):
        from services.analytics.crop_phenology import compute_gdd

        # max=8, min=2, base=10, upper=30 → GDD = min(8,30) - max(2,10) = 8-10 = -2 → 0
        gdd = compute_gdd(8, 2, base_temp=10.0, upper_temp=30.0)
        assert gdd == 0.0

    def test_gdd_zero_when_equal(self):
        from services.analytics.crop_phenology import compute_gdd

        gdd = compute_gdd(10, 10, base_temp=10.0, upper_temp=30.0)
        assert gdd == 0.0

    def test_gdd_large_range(self):
        from services.analytics.crop_phenology import compute_gdd

        gdd = compute_gdd(28, 12, base_temp=10.0, upper_temp=30.0)
        assert gdd == 16.0

    def test_gdd_negative_returns_zero(self):
        from services.analytics.crop_phenology import compute_gdd

        gdd = compute_gdd(5, 15, base_temp=10.0, upper_temp=30.0)
        assert gdd == 0.0


# ============================================================
# Crop-specific GDD
# ============================================================

class TestComputeGDDFromWeather:
    """Test crop-specific GDD computation."""

    def test_maize_gdd(self):
        from services.analytics.crop_phenology import compute_gdd_from_weather

        gdd = compute_gdd_from_weather(28.0, 16.0, "maize")
        assert gdd > 0

    def test_cassava_higher_base(self):
        from services.analytics.crop_phenology import compute_gdd_from_weather

        # Cassava base=15, so cold days contribute less
        gdd_maize = compute_gdd_from_weather(20.0, 8.0, "maize")  # base=10
        gdd_cassava = compute_gdd_from_weather(20.0, 8.0, "cassava")  # base=15

        assert gdd_maize > gdd_cassava

    def test_unknown_crop_uses_defaults(self):
        from services.analytics.crop_phenology import compute_gdd_from_weather

        gdd = compute_gdd_from_weather(25.0, 15.0, "unknown_crop")
        assert gdd > 0


# ============================================================
# Growth stage definitions
# ============================================================

class TestGetCropStages:
    """Test crop stage retrieval."""

    def test_maize_stages(self):
        from services.analytics.crop_phenology import get_crop_stages_from_config

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (None, None)

        stages = get_crop_stages_from_config(mock_conn, "maize")

        assert len(stages) >= 3
        assert stages[0]["name"] == "emergence"

    def test_bean_stages(self):
        from services.analytics.crop_phenology import get_crop_stages_from_config

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (None, None)

        stages = get_crop_stages_from_config(mock_conn, "beans")

        assert len(stages) >= 3
        assert any(s["name"] == "flowering" for s in stages)

    def test_stages_ordered_by_gdd(self):
        from services.analytics.crop_phenology import get_crop_stages_from_config

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (None, None)

        stages = get_crop_stages_from_config(mock_conn, "maize")

        gdds = [s.get("gdd", 0) for s in stages]
        assert gdds == sorted(gdds)


# ============================================================
# Current stage detection
# ============================================================

class TestGetCurrentStage:
    """Test current growth stage detection."""

    def _mock_db_with_weather(self, mock_conn, crop_name="Maize", planting_days_ago=60):
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        planting_date = date.today() - timedelta(days=planting_days_ago)

        # Crop cycle query
        mock_cursor.fetchone.side_effect = [
            # accumulate_gdd inner query
            (str(uuid.uuid4()), planting_date, "active", crop_name, 10.0, 30.0, 2500.0),
            # get_current_stage query
            (str(uuid.uuid4()), planting_date, "active", crop_name, 10.0, 30.0, 2500.0),
        ]

        # Weather data: 60 days of 28/16°C
        weather_rows = [
            (planting_date + timedelta(days=i), 28.0, 16.0)
            for i in range(planting_days_ago)
        ]

        # Third call: accumulate_gdd weather query
        mock_cursor.fetchall.return_value = weather_rows

        # Fourth call: get_current_stage stages query
        mock_cursor.fetchone.side_effect = [
            # accumulate_gdd inner
            (str(uuid.uuid4()), planting_date, "active", crop_name, 10.0, 30.0, 2500.0),
            # get_current_stage inner
            (str(uuid.uuid4()), planting_date, "active", crop_name, 10.0, 30.0, 2500.0),
        ]

        # Stage config query returns None (use defaults)
        mock_cursor.fetchone.side_effect = [
            # accumulate_gdd crop info
            (str(uuid.uuid4()), planting_date, "active", crop_name, 10.0, 30.0, 2500.0),
            # accumulate_gdd weather
            None,  # placeholder
            # get_current_stage crop info
            (str(uuid.uuid4()), planting_date, "active", crop_name, 10.0, 30.0, 2500.0),
            # get_current_stage stages config (None = use defaults)
            (None, None),
        ]

        mock_cursor.fetchall.return_value = weather_rows

    def test_returns_stage_name(self):
        from services.analytics.crop_phenology import get_current_stage

        mock_conn = MagicMock()
        self._mock_db_with_weather(mock_conn, planting_days_ago=60)

        result = get_current_stage(mock_conn, str(uuid.uuid4()))

        # After 60 days × ~12 GDD/day = ~720 GDD → vegetative stage
        assert "stage_name" in result
        assert result["accumulated_gdd"] > 0


# ============================================================
# Schedule anomaly detection
# ============================================================

class TestScheduleAnomalies:
    """Test schedule anomaly detection."""

    def test_no_anomalies_for_unknown_location(self):
        from services.analytics.crop_phenology import detect_schedule_anomalies

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        anomalies = detect_schedule_anomalies(mock_conn, str(uuid.uuid4()))
        assert anomalies == []


# ============================================================
# List stages
# ============================================================

class TestListStages:
    """Test stage listing."""

    def test_list_maize_stages(self):
        from services.analytics.crop_phenology import list_stages

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (None, None)

        stages = list_stages(mock_conn, "maize")

        assert len(stages) >= 3
        assert all("stage" in s for s in stages)
        assert all("gdd_threshold" in s for s in stages)


# ============================================================
# Estimate stage dates
# ============================================================

class TestEstimateStageDates:
    """Test stage date projection."""

    def test_returns_projections(self):
        from services.analytics.crop_phenology import estimate_stage_dates

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        planting_date = date.today() - timedelta(days=60)

        # Call order: estimate_stage_dates → get_crop_stages_from_config → accumulate_gdd
        mock_cursor.fetchone.side_effect = [
            # 1. estimate_stage_dates crop info
            (planting_date, "Maize", 2500.0, 10.0, 30.0),
            # 2. get_crop_stages_from_config crop_gdd_config query → None (use defaults)
            (None, None),
            # 3. accumulate_gdd crop info
            (str(uuid.uuid4()), planting_date, "active", "Maize", 10.0, 30.0, 2500.0),
        ]

        # Weather data for accumulate_gdd (returned by fetchall)
        mock_cursor.fetchall.return_value = [
            (planting_date + timedelta(days=i), 28.0, 16.0)
            for i in range(60)
        ]

        result = estimate_stage_dates(mock_conn, str(uuid.uuid4()))

        assert "projections" in result
        assert len(result["projections"]) >= 3
        assert result["accumulated_gdd"] > 0
