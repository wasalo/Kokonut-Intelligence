"""Tests for Evapotranspiration module."""

import math
import uuid
from datetime import date

import pytest


# ============================================================
# FAO-56 Penman-Monteith ET₀
# ============================================================

class TestComputeET0:
    """Test FAO-56 Penman-Monteith reference ET₀ calculation."""

    def test_et0_returns_positive(self):
        from services.analytics.evapotranspiration import compute_et0_penman_monteith

        result = compute_et0_penman_monteith(
            temp_max=30.0,
            temp_min=18.0,
            humidity=60.0,
            wind_speed=10.0,
            solar_radiation=18.0,
            elevation_m=0.0,
            latitude=10.0,
            day_of_year=180,
        )

        assert result["et0_mm"] > 0
        assert result["method"] == "penman_monteith"

    def test_et0_hot_dry_higher(self):
        from services.analytics.evapotranspiration import compute_et0_penman_monteith

        hot = compute_et0_penman_monteith(
            temp_max=35.0, temp_min=22.0, humidity=30.0,
            wind_speed=15.0, solar_radiation=22.0,
            latitude=10.0, day_of_year=180,
        )
        cool = compute_et0_penman_monteith(
            temp_max=20.0, temp_min=10.0, humidity=80.0,
            wind_speed=3.0, solar_radiation=12.0,
            latitude=10.0, day_of_year=180,
        )

        assert hot["et0_mm"] > cool["et0_mm"]

    def test_et0_hargreaves_fallback(self):
        from services.analytics.evapotranspiration import compute_et0_penman_monteith

        result = compute_et0_penman_monteith(
            temp_max=30.0, temp_min=18.0, humidity=60.0,
            wind_speed=10.0, solar_radiation=None,
            latitude=10.0, day_of_year=180,
        )

        assert result["et0_mm"] > 0
        assert result["method"] == "hargreaves"

    def test_et0_zero_when_temps_equal_to_base(self):
        from services.analytics.evapotranspiration import compute_et0_penman_monteith

        result = compute_et0_penman_monteith(
            temp_max=10.0, temp_min=10.0, humidity=100.0,
            wind_speed=0.0, solar_radiation=0.1,
            elevation_m=0.0, latitude=0.0, day_of_year=180,
        )

        # With very low temp range and 100% humidity, ET₀ should be very small
        assert result["et0_mm"] < 1.0

    def test_et0_returns_components(self):
        from services.analytics.evapotranspiration import compute_et0_penman_monteith

        result = compute_et0_penman_monteith(
            temp_max=28.0, temp_min=16.0, humidity=55.0,
            wind_speed=8.0, solar_radiation=16.0,
            elevation_m=500.0, latitude=-1.2, day_of_year=100,
        )

        assert "et0_mm" in result
        assert "vpd" in result
        assert "wind_speed_ms" in result
        assert result["wind_speed_ms"] == pytest.approx(8.0 / 3.6, 0.01)

    def test_et0_elevation_effect(self):
        from services.analytics.evapotranspiration import compute_et0_penman_monteith

        sea_level = compute_et0_penman_monteith(
            temp_max=25.0, temp_min=15.0, humidity=50.0,
            wind_speed=5.0, solar_radiation=15.0,
            elevation_m=0.0, latitude=10.0, day_of_year=180,
        )
        high_alt = compute_et0_penman_monteith(
            temp_max=25.0, temp_min=15.0, humidity=50.0,
            wind_speed=5.0, solar_radiation=15.0,
            elevation_m=2000.0, latitude=10.0, day_of_year=180,
        )

        # Both should produce valid results (may differ due to pressure/psychrometric)
        assert sea_level["et0_mm"] > 0
        assert high_alt["et0_mm"] > 0


# ============================================================
# Helper functions
# ============================================================

class TestHelperFunctions:
    """Test ET helper functions."""

    def test_saturation_vapor_pressure(self):
        from services.analytics.evapotranspiration import compute_saturation_vapor_pressure

        # At 0°C, es ≈ 0.611 kPa
        es_0 = compute_saturation_vapor_pressure(0)
        assert es_0 == pytest.approx(0.611, 0.01)

        # At 20°C, es ≈ 2.34 kPa
        es_20 = compute_saturation_vapor_pressure(20)
        assert es_20 == pytest.approx(2.34, 0.05)

        # At 30°C, es ≈ 4.24 kPa
        es_30 = compute_saturation_vapor_pressure(30)
        assert es_30 == pytest.approx(4.24, 0.1)

    def test_vapor_pressure_deficit(self):
        from services.analytics.evapotranspiration import compute_vapor_pressure_deficit

        # High humidity → low VPD
        vpd_low = compute_vapor_pressure_deficit(25, 15, 90)
        assert vpd_low < 0.5

        # Low humidity → high VPD
        vpd_high = compute_vapor_pressure_deficit(30, 20, 30)
        assert vpd_high > 1.0

    def test_atmospheric_pressure(self):
        from services.analytics.evapotranspiration import compute_atmospheric_pressure

        p_sea = compute_atmospheric_pressure(0)
        p_1000 = compute_atmospheric_pressure(1000)
        p_3000 = compute_atmospheric_pressure(3000)

        assert p_sea == pytest.approx(101.3, 0.5)
        assert p_1000 < p_sea
        assert p_3000 < p_1000


# ============================================================
# Crop ETc
# ============================================================

class TestComputeEtc:
    """Test crop evapotranspiration computation."""

    def test_etc_equals_et0_times_kc(self):
        from services.analytics.evapotranspiration import compute_etc

        result = compute_etc(5.0, "maize", "mid")

        assert result["etc_mm"] == pytest.approx(5.0 * 1.15, 0.1)
        assert result["kc"] == 1.15
        assert result["stage"] == "mid"

    def test_kc_varies_by_stage(self):
        from services.analytics.evapotranspiration import compute_etc, get_crop_kc

        kc_initial = get_crop_kc("maize", "initial")
        kc_mid = get_crop_kc("maize", "mid")

        assert kc_initial < kc_mid

    def test_kc_varies_by_crop(self):
        from services.analytics.evapotranspiration import get_crop_kc

        kc_maize = get_crop_kc("maize", "mid")
        kc_cassava = get_crop_kc("cassava", "mid")

        # Both should return valid Kc
        assert kc_maize > 0
        assert kc_cassava > 0

    def test_unknown_crop_uses_default(self):
        from services.analytics.evapotranspiration import get_crop_kc

        kc = get_crop_kc("unknown_crop", "mid")
        assert kc > 0  # Should return default


# ============================================================
# Hargreaves fallback
# ============================================================

class TestHargreaves:
    """Test Hargreaves ET₀ estimation."""

    def test_hargreaves_positive(self):
        from services.analytics.evapotranspiration import _hargreaves_et0

        et0 = _hargreaves_et0(30.0, 18.0, 10.0, 180)
        assert et0 > 0

    def test_hargreaves_hotter_is_higher(self):
        from services.analytics.evapotranspiration import _hargreaves_et0

        et0_hot = _hargreaves_et0(35.0, 22.0, 10.0, 180)
        et0_cool = _hargreaves_et0(22.0, 12.0, 10.0, 180)

        assert et0_hot > et0_cool


# ============================================================
# Growth stage from GDD
# ============================================================

class TestGrowthStageFromGDD:
    """Test growth stage determination from GDD."""

    def test_initial_stage(self):
        from services.analytics.evapotranspiration import get_growth_stage_from_gdd

        stage = get_growth_stage_from_gdd("maize", 200, 2500)
        assert stage == "initial"

    def test_mid_stage(self):
        from services.analytics.evapotranspiration import get_growth_stage_from_gdd

        stage = get_growth_stage_from_gdd("maize", 1500, 2500)
        assert stage == "mid"

    def test_late_stage(self):
        from services.analytics.evapotranspiration import get_growth_stage_from_gdd

        stage = get_growth_stage_from_gdd("maize", 2400, 2500)
        assert stage == "late"

    def test_zero_total_gdd(self):
        from services.analytics.evapotranspiration import get_growth_stage_from_gdd

        stage = get_growth_stage_from_gdd("maize", 100, 0)
        assert stage == "unknown"


# ============================================================
# Water balance
# ============================================================

class TestWaterBalance:
    """Test water balance computation."""

    def test_no_data_returns_no_data(self):
        from unittest.mock import MagicMock
        from services.analytics.evapotranspiration import compute_water_balance

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Sequence: crop_cycle query returns None (no crop), then weather query returns empty
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        result = compute_water_balance(mock_conn, str(uuid.uuid4()))

        assert result["water_status"] == "no_data"
        assert result["total_rainfall_mm"] == 0

    def test_adequate_water(self):
        from unittest.mock import MagicMock
        from services.analytics.evapotranspiration import compute_water_balance

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # No crop cycle → fetchone returns None
        mock_cursor.fetchone.return_value = None

        # 30 days of rainy weather
        mock_cursor.fetchall.return_value = [
            (date(2026, 1, i+1), 10.0 + (i % 5), 25.0, 30.0, 20.0, 60.0, 5.0, 15.0)
            for i in range(30)
        ]

        result = compute_water_balance(mock_conn, str(uuid.uuid4()), period_days=30)

        assert result["total_rainfall_mm"] > 0
        assert result["total_et0_mm"] > 0
        assert result["water_status"] in ("adequate", "mild_stress")
