"""Data freshness monitoring tests."""

from datetime import datetime, timezone
from pathlib import Path

SCHEMA = Path("schemas/postgres/077_telemetry_infrastructure.sql")
SEED = Path("schemas/seeds/077_telemetry_infrastructure.sql")
ALERT_MIGRATION = Path("schemas/postgres/341_freshness_alert_durability.sql")


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


def test_freshness_alert_durability_migration() -> None:
    content = ALERT_MIGRATION.read_text()
    for table in (
        "data_freshness_alert_state",
        "data_freshness_alert_history",
        "data_freshness_alert_delivery_attempt",
    ):
        assert table in content
    assert "COALESCE(location_id" in content
    assert "alert_cooldown_minutes" in content
    assert "escalation_cooldown_minutes" in content


def test_freshness_persists_delivery_attempts() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "_persist_delivery_attempt" in content
    assert "attempt[\"error\"]" in content


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


def test_alert_event_deduplicates_until_cooldown() -> None:
    from datetime import timedelta

    from services.ingestion.data_freshness import _alert_event

    now = datetime.now(timezone.utc)
    assert _alert_event("fresh", "stale", None, None, now, 60, 15) == "alert"
    assert _alert_event("stale", "stale", "stale", now, now + timedelta(minutes=59), 60, 15) is None
    assert _alert_event("stale", "stale", "stale", now, now + timedelta(minutes=60), 60, 15) == "alert"


def test_alert_event_escalates_and_recovers() -> None:
    from services.ingestion.data_freshness import _alert_event

    now = datetime.now(timezone.utc)
    assert _alert_event("stale", "critical", "stale", now, now, 60, 15) == "escalation"
    assert _alert_event("critical", "fresh", "critical", now, now, 60, 15) == "recovery"


def test_alert_event_is_scope_agnostic() -> None:
    """Scope identity belongs to the persisted state key, not event classification."""
    from services.ingestion.data_freshness import _alert_event

    assert _alert_event(None, "stale", None, None, datetime.now(timezone.utc), 60, 15) == "alert"


def test_determine_status_boundary_fresh_stale() -> None:
    from services.ingestion.data_freshness import _determine_status

    assert _determine_status(30, 30, 60) == "fresh"
    assert _determine_status(31, 30, 60) == "stale"


def test_determine_status_boundary_stale_critical() -> None:
    from services.ingestion.data_freshness import _determine_status

    assert _determine_status(60, 30, 60) == "stale"
    assert _determine_status(61, 30, 60) == "critical"


def test_freshness_threshold_validation() -> None:
    from services.ingestion.data_freshness import _validate_thresholds

    _validate_thresholds(30, 60)
    for thresholds in ((0, 60), (30, 0), (61, 60)):
        try:
            _validate_thresholds(*thresholds)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid freshness thresholds were accepted")


def test_scoped_freshness_query_requires_location() -> None:
    from services.ingestion.data_freshness import _query_latest_data_at

    try:
        _query_latest_data_at(None, "remote_sensing", True)
    except ValueError:
        pass
    else:
        raise AssertionError("scoped freshness query did not require a location")


def test_freshness_config_defaults() -> None:
    content = SEED.read_text()
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
        "msavi",
        "satvi",
        "bsi",
        "nbr2",
        "ndti",
        "lswi",
        "brightness_index",
        "tc_brightness",
        "tc_greenness",
        "tc_wetness",
        "band_blue",
        "band_green",
        "band_red",
        "band_nir",
        "band_swir1",
        "band_swir2",
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
