"""Regression tests for P2 ingestion reliability protections."""

from pathlib import Path


def test_ingestion_reliability_indexes_are_database_backed():
    schema = Path("schemas/postgres/300_ingestion_reliability.sql").read_text()
    assert "uq_remote_sensing_observation_source" in schema
    assert "uq_price_observation_source_period" in schema
    assert "uq_sensor_reading_timestamp" in schema


def test_remote_sensing_due_jobs_use_the_signed_worker_claim():
    legacy = Path("services/ingestion/remote_sensing_fetcher.py").read_text()
    worker = Path("services/ingestion/remote_sensing_worker.py").read_text()
    migration = Path("schemas/postgres/432_signed_remote_sensing_worker.sql").read_text()
    assert "legacy remote-sensing due-job execution is disabled" in legacy
    assert "kokonut_security.claim_remote_sensing_job(%s::uuid)" in worker
    assert "CREATE OR REPLACE FUNCTION kokonut_security.claim_remote_sensing_job" in migration


def test_ingestion_entry_points_close_connections_in_finally():
    remote = Path("services/ingestion/remote_sensing.py").read_text()
    market = Path("services/ingestion/market_data.py").read_text()
    assert remote.count("finally:") >= 1
    assert market.count("finally:") >= 2
    assert "ON CONFLICT (source_system, source_id)" in remote
    assert "ON CONFLICT (source, commodity_code, market_name, price_date)" in market


def test_sensor_duplicate_key_normalizes_missing_time():
    content = Path("services/ingestion/sensor_ingester.py").read_text()
    assert 'reading_time = reading_time or "00:00:00"' in content
    assert "ON CONFLICT (sensor_id, reading_date, reading_time)" in content
