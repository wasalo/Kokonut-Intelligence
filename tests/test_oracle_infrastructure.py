"""Oracle infrastructure tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/081_oracle_infrastructure.sql")


def test_schema_has_price_observation_extensions() -> None:
    content = SCHEMA.read_text()
    assert "confidence" in content
    assert "deviation_pct" in content
    assert "source_count" in content
    assert "aggregation_method" in content


def test_schema_has_alert_rule_extensions() -> None:
    content = SCHEMA.read_text()
    assert "actuator_enabled" in content
    assert "actuator_type" in content
    assert "actuator_command" in content
    assert "human_approval_required" in content


def test_schema_has_sensor_alert_extensions() -> None:
    content = SCHEMA.read_text()
    assert "actuation_sent" in content
    assert "actuation_response" in content
    assert "actuation_status" in content


def test_schema_has_oracle_price_log() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS oracle_price_log" in content
    assert "commodity" in content
    assert "attestation_uid" in content


def test_schema_has_actuation_log() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS actuation_log" in content
    assert "human_approval_required" in content
    assert "approved_by" in content
    assert "actuation_status" in content


def test_oracle_aggregator_exists() -> None:
    assert Path("services/ingestion/oracle_aggregator.py").exists()


def test_oracle_aggregator_has_consensus() -> None:
    from services.ingestion.oracle_aggregator import median_consensus, weighted_average_consensus
    assert callable(median_consensus)
    assert callable(weighted_average_consensus)


def test_median_consensus_basic() -> None:
    from datetime import datetime, timezone

    from services.ingestion.oracle_aggregator import PriceReading, median_consensus

    readings = [
        PriceReading("world_bank", 100.0, datetime.now(timezone.utc)),
        PriceReading("yahoo_finance", 102.0, datetime.now(timezone.utc)),
        PriceReading("usda", 99.0, datetime.now(timezone.utc)),
    ]
    result = median_consensus(readings, commodity="COFFEE")
    assert result is not None
    assert result.source == "consensus"
    assert result.source_count == 3
    assert result.confidence > 0.8


def test_median_consensus_rejects_outlier() -> None:
    from datetime import datetime, timezone

    from services.ingestion.oracle_aggregator import PriceReading, median_consensus

    readings = [
        PriceReading("world_bank", 100.0, datetime.now(timezone.utc)),
        PriceReading("yahoo_finance", 102.0, datetime.now(timezone.utc)),
        PriceReading("bad_source", 200.0, datetime.now(timezone.utc)),  # outlier
    ]
    result = median_consensus(readings, max_deviation_pct=15.0, commodity="COFFEE")
    assert result is not None
    assert "bad_source" in result.sources_rejected
    assert result.source_count == 2


def test_median_consensus_empty() -> None:
    from services.ingestion.oracle_aggregator import median_consensus
    assert median_consensus([]) is None


def test_median_consensus_rejects_invalid_prices_and_naive_timestamps() -> None:
    from datetime import datetime, timezone

    from services.ingestion.oracle_aggregator import PriceReading, median_consensus

    timestamp = datetime.now(timezone.utc)
    readings = [
        PriceReading("source_a", 100.0, timestamp),
        PriceReading("source_b", 101.0, timestamp),
        PriceReading("source_nan", float("nan"), timestamp),
        PriceReading("source_negative", -10.0, timestamp),
        PriceReading("source_naive", 99.0, datetime(2026, 1, 1)),
    ]

    result = median_consensus(readings, commodity="COFFEE")

    assert result is not None
    assert result.source_count == 2
    assert result.sources_used == ["source_a", "source_b"]
    assert set(result.sources_rejected) == {"source_nan", "source_negative", "source_naive"}
    assert result.metadata["invalid_or_duplicate_reading_count"] == 3


def test_median_consensus_counts_each_source_once() -> None:
    from datetime import datetime, timezone

    from services.ingestion.oracle_aggregator import PriceReading, median_consensus

    timestamp = datetime.now(timezone.utc)
    readings = [
        PriceReading("provider_a", 100.0, timestamp),
        PriceReading(" PROVIDER_A ", 200.0, timestamp),
        PriceReading("provider_b", 101.0, timestamp),
        PriceReading("provider_c", 99.0, timestamp),
    ]

    result = median_consensus(readings, commodity="COFFEE")

    assert result is not None
    assert result.source_count == 2
    assert result.sources_used == ["provider_b", "provider_c"]
    assert [source.casefold() for source in result.sources_rejected] == ["provider_a"]


def test_median_consensus_rejects_invalid_deviation_thresholds() -> None:
    from datetime import datetime, timezone

    from services.ingestion.oracle_aggregator import PriceReading, median_consensus

    readings = [PriceReading("source", 100.0, datetime.now(timezone.utc))]

    assert median_consensus(readings, max_deviation_pct=-1) is None
    assert median_consensus(readings, max_deviation_pct=float("nan")) is None
    assert median_consensus(readings, max_deviation_pct=True) is None


def test_weighted_consensus_rejects_invalid_and_zero_weight_sources() -> None:
    from datetime import datetime, timezone

    from services.ingestion.oracle_aggregator import PriceReading, weighted_average_consensus

    timestamp = datetime.now(timezone.utc)
    readings = [
        PriceReading("valid", 100.0, timestamp, confidence=0.5),
        PriceReading("bad-confidence", 500.0, timestamp, confidence=1.5),
        PriceReading("zero-weight", 10000.0, timestamp, confidence=0.0),
    ]

    result = weighted_average_consensus(readings, commodity="COFFEE")

    assert result is not None
    assert result.price == 100.0
    assert result.source_count == 1
    assert result.sources_used == ["valid"]
    assert set(result.sources_rejected) == {"bad-confidence", "zero-weight"}
    assert result.metadata["zero_weight_source_count"] == 1


def test_yahoo_finance_exists() -> None:
    assert Path("services/ingestion/yahoo_finance.py").exists()


def test_yahoo_finance_has_tickers() -> None:
    from services.ingestion.yahoo_finance import YAHOO_TICKERS
    assert "COFFEE" in YAHOO_TICKERS
    assert "COCOA" in YAHOO_TICKERS
    assert "MAIZE" in YAHOO_TICKERS
    assert YAHOO_TICKERS["COFFEE"] == "KC=F"


def test_price_attestation_exists() -> None:
    assert Path("services/ingestion/price_attestation.py").exists()


def test_price_attestation_has_schema() -> None:
    from services.ingestion.price_attestation import PRICE_FEED_SCHEMA
    assert "commodity" in PRICE_FEED_SCHEMA["schema"]
    assert "price" in PRICE_FEED_SCHEMA["schema"]
    assert PRICE_FEED_SCHEMA["revocable"] is True


def test_mqtt_actuator_exists() -> None:
    assert Path("services/ingestion/mqtt_actuator.py").exists()


def test_mqtt_actuator_has_build_command() -> None:
    from services.ingestion.mqtt_actuator import build_actuation_command
    cmd = build_actuation_command("dev001", "irrigation", "start", {"duration": 30})
    assert cmd["device_id"] == "dev001"
    assert cmd["actuator_type"] == "irrigation"
    assert cmd["command"] == "start"
    assert cmd["parameters"]["duration"] == 30


def test_mqtt_actuator_has_send_command() -> None:
    from services.ingestion.mqtt_actuator import send_actuation_command
    assert callable(send_actuation_command)


def test_mqtt_actuator_has_approve() -> None:
    from services.ingestion.mqtt_actuator import approve_actuation
    assert callable(approve_actuation)


def test_mqtt_actuator_has_publish() -> None:
    from services.ingestion.mqtt_actuator import publish_to_mqtt
    assert callable(publish_to_mqtt)


def test_mqtt_actuator_topic_pattern() -> None:
    from services.ingestion.mqtt_actuator import ACTUATOR_TOPIC
    topic = ACTUATOR_TOPIC.format(location_id="loc1", actuator_type="irrigation")
    assert "loc1" in topic
    assert "irrigation" in topic
    assert "actuators" in topic


def test_gee_climate_exists() -> None:
    assert Path("services/ingestion/gee_climate.py").exists()


def test_gee_climate_has_all_fetchers() -> None:
    from services.ingestion.gee_climate import (
        fetch_all_climate,
        fetch_era5_land,
        fetch_modis_lst,
        fetch_sentinel1_sar,
        fetch_smap_moisture,
    )
    assert callable(fetch_modis_lst)
    assert callable(fetch_smap_moisture)
    assert callable(fetch_sentinel1_sar)
    assert callable(fetch_era5_land)
    assert callable(fetch_all_climate)


def test_gee_climate_has_era5_dataset() -> None:
    content = Path("services/ingestion/gee_climate.py").read_text()
    assert "ECMWF/ERA5_LAND/DAILY_AGGR" in content
    assert "temperature_2m" in content
    assert "total_precipitation_sum" in content


def test_gee_climate_has_modis_dataset() -> None:
    content = Path("services/ingestion/gee_climate.py").read_text()
    assert "MODIS/061/MOD11A2" in content
    assert "LST_Day_1km" in content


def test_gee_climate_has_smap_dataset() -> None:
    content = Path("services/ingestion/gee_climate.py").read_text()
    assert "NASA/SMAP/SPL3SMP_E/006" in content
    assert "soil_moisture_pm" in content


def test_gee_climate_has_sentinel1_dataset() -> None:
    content = Path("services/ingestion/gee_climate.py").read_text()
    assert "COPERNICUS/S1_GRD" in content
    assert "VV" in content
    assert "VH" in content


def test_gee_climate_dual_writes() -> None:
    content = Path("services/ingestion/gee_climate.py").read_text()
    assert "log_ingestion" in content
    assert "INSERT INTO" in content


def test_climate_data_updated_to_gee() -> None:
    content = Path("services/ingestion/climate_data.py").read_text()
    assert "gee_climate" in content
    assert "fetch_era5_land" in content
    assert "fetch_modis_lst" in content
    assert "fetch_smap_moisture" in content
    assert "fetch_sentinel1_sar" in content


def test_anomaly_detector_has_actuation() -> None:
    content = Path("services/ingestion/anomaly_detector.py").read_text()
    assert "send_actuation_commands" in content
    assert "actuator_enabled" in content
    assert "human_approval_required" in content


def test_requirements_has_yfinance() -> None:
    content = Path("requirements.txt").read_text()
    assert "yfinance" in content


def test_price_feed_flow_exists() -> None:
    assert Path("services/flows/price_feed.py").exists()


def test_price_feed_flow_has_decorator() -> None:
    content = Path("services/flows/price_feed.py").read_text()
    assert "@flow" in content
    assert "retries" in content


def test_actuation_log_has_safety_guardrails() -> None:
    content = SCHEMA.read_text()
    assert "human_approval_required" in content
    assert "requires_approval" in content
    assert "approved_by" in content


def test_schema_has_aggregation_method_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_price_obs_aggregation" in content
    assert "median_consensus" in content
