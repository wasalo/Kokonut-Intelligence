-- P2 ingestion reliability: enforce idempotent source and reading identities.
CREATE UNIQUE INDEX IF NOT EXISTS uq_remote_sensing_observation_source
    ON remote_sensing_observation (source_system, source_id)
    WHERE source_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_price_observation_source_period
    ON price_observation (source, commodity_code, market_name, price_date);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sensor_reading_timestamp
    ON sensor_reading (sensor_id, reading_date, reading_time);
