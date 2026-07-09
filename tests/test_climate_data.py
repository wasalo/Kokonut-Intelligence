"""Climate data ingestion tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/077_telemetry_infrastructure.sql")


def test_schema_file_exists() -> None:
    assert SCHEMA.exists()


def test_estimate_bioclim_tropical() -> None:
    from services.ingestion.climate_data import _estimate_bioclim
    # Tropical latitude (near equator)
    bio1 = _estimate_bioclim(0.0, 36.0, 1)
    assert bio1 is not None
    assert bio1 > 20  # Should be warm


def test_estimate_bioclim_temperate() -> None:
    from services.ingestion.climate_data import _estimate_bioclim
    # Temperate latitude
    bio1 = _estimate_bioclim(45.0, 0.0, 1)
    assert bio1 is not None
    assert bio1 < 25  # Should be cooler than tropical


def test_estimate_bioclim_arctic() -> None:
    from services.ingestion.climate_data import _estimate_bioclim
    # Arctic latitude
    bio1 = _estimate_bioclim(70.0, 0.0, 1)
    assert bio1 is not None
    assert bio1 < 5  # Should be cold


def test_estimate_bioclim_all_variables() -> None:
    from services.ingestion.climate_data import _estimate_bioclim
    for bio in range(1, 20):
        value = _estimate_bioclim(10.0, 36.0, bio)
        assert value is not None, f"bio_{bio} returned None"


def test_estimate_bioclim_temperature_range() -> None:
    from services.ingestion.climate_data import _estimate_bioclim
    # Temperature variables (bio 1-11) should be reasonable
    for bio in range(1, 12):
        value = _estimate_bioclim(10.0, 36.0, bio)
        if value is not None:
            assert -50 < value < 60, f"bio_{bio} = {value} outside reasonable range"


def test_estimate_bioclim_precipitation_range() -> None:
    from services.ingestion.climate_data import _estimate_bioclim
    # Precipitation variables (bio 12-19) should be non-negative
    for bio in range(12, 20):
        value = _estimate_bioclim(10.0, 36.0, bio)
        if value is not None:
            assert value >= 0, f"bio_{bio} = {value} is negative"


def test_worldclim_insert_pattern() -> None:
    """Verify WorldClim insert uses ON CONFLICT for idempotency."""
    content = Path("services/ingestion/climate_data.py").read_text()
    assert "ON CONFLICT (location_id) DO UPDATE SET" in content


def test_climate_data_has_cli() -> None:
    content = Path("services/ingestion/climate_data.py").read_text()
    assert 'if __name__ == "__main__":' in content
    assert "--worldclim" in content
    assert "--location-id" in content


def test_freshness_has_cli() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert 'if __name__ == "__main__":' in content
    assert "--check" in content
    assert "--summary" in content


def test_freshness_uses_logging() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "get_logger" in content


def test_climate_data_uses_logging() -> None:
    content = Path("services/ingestion/climate_data.py").read_text()
    assert "get_logger" in content


def test_freshness_queries_config_table() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "data_freshness_config" in content


def test_freshness_inserts_check_results() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "data_freshness_check" in content


def test_freshness_has_alert_channels() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "webhook" in content or "ALERT_WEBHOOK_URL" in content
    assert "email" in content or "ALERT_SMTP" in content


def test_climate_data_inserts_all_tables() -> None:
    content = Path("services/ingestion/climate_data.py").read_text()
    assert "worldclim_climate" in content
    assert "ncep_weather_summary" in content
    assert "modis_lst_summary" in content
    assert "smap_soil_moisture" in content
    assert "sentinel1_sar_summary" in content


def test_rs_job_schema_has_provider_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_rs_job_provider" in content
    assert "'gee'" in content
    assert "'copernicus'" in content
