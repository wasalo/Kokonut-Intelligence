"""Tests for spectral index computation (SATVI, BSI, NBR2, NDTI, LSWI, tasseled cap)."""

from pathlib import Path

from services.analytics.spectral_indices import (
    compute_all_indices,
    compute_bsi,
    compute_brightness_index,
    compute_lswi,
    compute_nbr2,
    compute_ndti,
    compute_satvi,
    compute_tasseled_cap,
)

SCHEMA = Path("schemas/postgres/074_dsm_soc_prediction.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_adds_spectral_columns() -> None:
    text = SCHEMA.read_text()
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS satvi" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS bsi" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS nbr2" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS ndti" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS lswi" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS tc_brightness" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS tc_greenness" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS tc_wetness" in text


def test_schema_defines_dsm_tables() -> None:
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS worldclim_climate" in text
    assert "CREATE TABLE IF NOT EXISTS ncep_weather_summary" in text
    assert "CREATE TABLE IF NOT EXISTS modis_lst_summary" in text
    assert "CREATE TABLE IF NOT EXISTS smap_soil_moisture" in text
    assert "CREATE TABLE IF NOT EXISTS sentinel1_sar_summary" in text
    assert "CREATE TABLE IF NOT EXISTS soc_prediction_model" in text
    assert "CREATE TABLE IF NOT EXISTS soc_prediction" in text
    assert "CREATE TABLE IF NOT EXISTS computed_feature_importance" in text
    assert "CREATE TABLE IF NOT EXISTS cv_fold_result" in text


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    assert "CREATE OR REPLACE VIEW v_public_soc_predictions" in text
    assert "CREATE OR REPLACE VIEW v_soc_model_performance" in text
    assert "CREATE OR REPLACE VIEW v_feature_importance_summary" in text
    assert "CREATE OR REPLACE VIEW v_cv_summary" in text
    assert "CREATE OR REPLACE VIEW v_spectral_index_stats" in text


def test_schema_has_raw_band_columns() -> None:
    text = SCHEMA.read_text()
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_blue" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_green" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_red" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_nir" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_swir1" in text
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_swir2" in text


# ---------------------------------------------------------------------------
# SATVI tests
# ---------------------------------------------------------------------------

def test_satvi_basic() -> None:
    result = compute_satvi(swir1=0.2, red=0.1, swir2=0.05)
    # 1.5 * (0.2 - 0.1) / (0.2 + 0.1 + 0.5) - 0.05/2 = 1.5 * 0.1/0.8 - 0.025 = 0.1875 - 0.025 = 0.1625
    assert result is not None
    assert abs(result - 0.1625) < 0.001


def test_satvi_zero_denominator() -> None:
    result = compute_satvi(swir1=0.0, red=0.0, swir2=0.0)
    assert result == 0.0


# ---------------------------------------------------------------------------
# BSI tests
# ---------------------------------------------------------------------------

def test_bsi_basic() -> None:
    result = compute_bsi(red=0.3, swir1=0.2, nir=0.1, blue=0.05)
    # (0.3 + 0.2 - 0.1 - 0.05) / (0.3 + 0.2 + 0.1 + 0.05) = 0.35 / 0.65
    assert result is not None
    assert abs(result - 0.5385) < 0.001


def test_bsi_zero_denominator() -> None:
    result = compute_bsi(red=0.0, swir1=0.0, nir=0.0, blue=0.0)
    assert result is None


# ---------------------------------------------------------------------------
# NBR2 tests
# ---------------------------------------------------------------------------

def test_nbr2_basic() -> None:
    result = compute_nbr2(nir=0.4, swir2=0.1)
    # (0.4 - 0.1) / (0.4 + 0.1) = 0.6
    assert result == 0.6


def test_nbr2_equal_bands() -> None:
    result = compute_nbr2(nir=0.3, swir2=0.3)
    assert result == 0.0


# ---------------------------------------------------------------------------
# NDTI tests
# ---------------------------------------------------------------------------

def test_ndti_basic() -> None:
    result = compute_ndti(swir1=0.25, swir2=0.15)
    # (0.25 - 0.15) / (0.25 + 0.15) = 0.25
    assert result == 0.25


# ---------------------------------------------------------------------------
# LSWI tests
# ---------------------------------------------------------------------------

def test_lswi_basic() -> None:
    result = compute_lswi(nir=0.4, swir1=0.2)
    # (0.4 - 0.2) / (0.4 + 0.2) = 0.3333
    assert result is not None
    assert abs(result - 0.3333) < 0.001


# ---------------------------------------------------------------------------
# Tasseled cap tests
# ---------------------------------------------------------------------------

def test_tasseled_cap_basic() -> None:
    result = compute_tasseled_cap(0.05, 0.08, 0.06, 0.25, 0.15, 0.10)
    assert "tc_brightness" in result
    assert "tc_greenness" in result
    assert "tc_wetness" in result
    assert isinstance(result["tc_brightness"], float)
    assert isinstance(result["tc_greenness"], float)
    assert isinstance(result["tc_wetness"], float)


def test_tasseled_cap_zero_bands() -> None:
    result = compute_tasseled_cap(0, 0, 0, 0, 0, 0)
    assert result["tc_brightness"] == 0.0
    assert result["tc_greenness"] == 0.0
    assert result["tc_wetness"] == 0.0


# ---------------------------------------------------------------------------
# compute_all_indices tests
# ---------------------------------------------------------------------------

def test_compute_all_indices() -> None:
    bands = {
        "blue": 0.05,
        "green": 0.08,
        "red": 0.06,
        "nir": 0.25,
        "swir1": 0.15,
        "swir2": 0.10,
    }
    result = compute_all_indices(bands)
    assert "ndvi" in result
    assert "savi" in result
    assert "satvi" in result
    assert "bsi" in result
    assert "nbr2" in result
    assert "ndti" in result
    assert "lswi" in result
    assert "brightness_index" in result
    assert "tc_brightness" in result
    assert "tc_greenness" in result
    assert "tc_wetness" in result
    # NDVI should be positive (nir > red)
    assert result["ndvi"] > 0


def test_compute_all_indices_missing_bands() -> None:
    result = compute_all_indices({"blue": 0.05})
    assert result["ndvi"] is None
    # SATVI returns 0.0 when swir1=0, red=0 (zero denominator is 0.5, not 0)
    assert result["satvi"] == 0.0


# ---------------------------------------------------------------------------
# Brightness index tests
# ---------------------------------------------------------------------------

def test_brightness_index() -> None:
    result = compute_brightness_index(red=0.3, green=0.4)
    # sqrt((0.09 + 0.16) / 2) = sqrt(0.125) ≈ 0.3536
    assert result is not None
    assert abs(result - 0.3536) < 0.001


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_adds_spectral_columns()
    test_schema_defines_dsm_tables()
    test_schema_defines_views()
    test_schema_has_raw_band_columns()
    test_satvi_basic()
    test_satvi_zero_denominator()
    test_bsi_basic()
    test_bsi_zero_denominator()
    test_nbr2_basic()
    test_nbr2_equal_bands()
    test_ndti_basic()
    test_lswi_basic()
    test_tasseled_cap_basic()
    test_tasseled_cap_zero_bands()
    test_compute_all_indices()
    test_compute_all_indices_missing_bands()
    test_brightness_index()
    print("All tests passed.")
