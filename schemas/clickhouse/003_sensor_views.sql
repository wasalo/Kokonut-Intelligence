-- ============================================================
-- ClickHouse: Sensor Analytics Materialized Views
-- ============================================================

-- Daily sensor summary (per location per day)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_sensor_summary
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (day, location_id, sensor_type)
AS SELECT
    toDate(timestamp) AS day,
    location_id,
    sensor_type,
    avg(value) AS avg_value,
    min(value) AS min_value,
    max(value) AS max_value,
    count() AS total_readings,
    uniq(sensor_id) AS active_sensors,
    countIf(quality != 'good') AS suspect_readings
FROM sensor_readings
GROUP BY day, location_id, sensor_type;

-- Sensor reading rate (readings per hour per sensor type)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sensor_reading_rate
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, sensor_type)
AS SELECT
    toStartOfHour(timestamp) AS hour,
    sensor_type,
    count() AS total_readings,
    uniq(sensor_id) AS active_sensors,
    uniq(location_id) AS active_locations
FROM sensor_readings
GROUP BY hour, sensor_type;
