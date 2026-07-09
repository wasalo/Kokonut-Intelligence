"""Data freshness monitoring tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/077_telemetry_infrastructure.sql")


def test_schema_file_exists() -> None:
    assert SCHEMA.exists(), f"Schema file not found: {SCHEMA}"


def test_schema_contains_tables() -> None:
    content = SCHEMA.read_text()
    expected_tables = [
        "data_freshness_config",
        "data_freshness_check",
        "remote_sensing_job",
        "sensor_device_health",
    ]
    for table in expected_tables:
        assert table in content, f"Table {table} not found in schema"


def test_schema_contains_views() -> None:
    content = SCHEMA.read_text()
    assert "v_data_freshness_summary" in content
    assert "v_sensor_device_health_summary" in content


def test_determine_status_fresh() -> None:
    from services.ingestion.data_freshness import _determine_status
    assert _determine_status(10, 30, 60) == "fresh"
    assert _determine_status(30, 30, 60) == "fresh"
    assert _determine_status(0, 30, 60) == "fresh"


def test_determine_status_stale() -> None:
    from services.ingestion.data_freshness import _determine_status
    assert _determine_status(31, 30, 60) == "stale"
    assert _determine_status(60, 30, 60) == "stale"


def test_determine_status_critical() -> None:
    from services.ingestion.data_freshness import _determine_status
    assert _determine_status(61, 30, 60) == "critical"
    assert _determine_status(120, 30, 60) == "critical"


def test_determine_status_no_data() -> None:
    from services.ingestion.data_freshness import _determine_status
    assert _determine_status(None, 30, 60) == "no_data"


def test_determine_status_boundary_fresh_stale() -> None:
    from services.ingestion.data_freshness import _determine_status
    assert _determine_status(30, 30, 60) == "fresh"
    assert _determine_status(31, 30, 60) == "stale"


def test_determine_status_boundary_stale_critical() -> None:
    from services.ingestion.data_freshness import _determine_status
    assert _determine_status(60, 30, 60) == "stale"
    assert _determine_status(61, 30, 60) == "critical"


def test_freshness_config_defaults() -> None:
    content = SCHEMA.read_text()
    # Check that default SLAs are seeded
    assert "weather" in content
    assert "sensors" in content
    assert "remote_sensing" in content
    assert "market_data" in content
    assert "eas_indexer" in content
    assert "rpc_indexer" in content
    assert "gnosis_indexer" in content


def test_freshness_thresholds_monotonic() -> None:
    """Stale threshold <= Critical threshold."""
    from services.ingestion.data_freshness import _determine_status
    # For any gap between stale and critical, status should be stale
    stale_threshold = 30
    critical_threshold = 60
    assert _determine_status(45, stale_threshold, critical_threshold) == "stale"
    # For gap above critical, status should be critical
    assert _determine_status(90, stale_threshold, critical_threshold) == "critical"


def test_climate_data_schema_exists() -> None:
    from pathlib import Path
    rs_job = Path("schemas/postgres/077_telemetry_infrastructure.sql")
    content = rs_job.read_text()
    assert "remote_sensing_job" in content
    assert "provider" in content
    assert "cadence_days" in content


def test_sensor_device_health_schema() -> None:
    from pathlib import Path
    rs_job = Path("schemas/postgres/077_telemetry_infrastructure.sql")
    content = rs_job.read_text()
    assert "sensor_device_health" in content
    assert "battery_pct" in content
    assert "signal_strength_dbm" in content
    assert "reading_rate_per_hour" in content


def test_clickhouse_sync_file_exists() -> None:
    ch_sync = Path("schemas/clickhouse/006_telemetry_sync.sql")
    assert ch_sync.exists(), f"ClickHouse sync file not found: {ch_sync}"


def test_clickhouse_sync_adds_columns() -> None:
    ch_sync = Path("schemas/clickhouse/006_telemetry_sync.sql")
    content = ch_sync.read_text()
    expected_columns = [
        "msavi", "satvi", "bsi", "nbr2", "ndti", "lswi",
        "brightness_index", "tc_brightness", "tc_greenness", "tc_wetness",
        "band_blue", "band_green", "band_red", "band_nir", "band_swir1", "band_swir2",
        "source_system",
    ]
    for col in expected_columns:
        assert col in content, f"Column {col} not found in ClickHouse sync"


def test_clickhouse_materialized_view() -> None:
    ch_sync = Path("schemas/clickhouse/006_telemetry_sync.sql")
    content = ch_sync.read_text()
    assert "mv_daily_remote_sensing_summary" in content
    assert "v_remote_sensing_freshness" in content


def test_seed_file_exists() -> None:
    seed = Path("schemas/seeds/077_telemetry_infrastructure.sql")
    assert seed.exists(), f"Seed file not found: {seed}"


def test_seed_has_freshness_configs() -> None:
    seed = Path("schemas/seeds/077_telemetry_infrastructure.sql")
    content = seed.read_text()
    assert "data_freshness_config" in content
    assert "expected_interval_minutes" in content


def test_seed_has_remote_sensing_job() -> None:
    seed = Path("schemas/seeds/077_telemetry_infrastructure.sql")
    content = seed.read_text()
    assert "remote_sensing_job" in content
    assert "gee" in content
