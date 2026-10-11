-- Read corrected statistics directly from deduplicated raw rows.
-- V2 aggregate-state targets can overcount crash replays on this ClickHouse version.
CREATE VIEW IF NOT EXISTS v_daily_sensor_summary_v3 AS
SELECT toDate(timestamp) AS day, location_id, sensor_type,
    avg(value) AS avg_value, min(value) AS min_value, max(value) AS max_value,
    count() AS total_readings, uniqExact(sensor_id) AS active_sensors,
    countIf(quality != 'good') AS suspect_readings
FROM sensor_readings GROUP BY day, location_id, sensor_type;

CREATE VIEW IF NOT EXISTS v_sensor_reading_rate_v3 AS
SELECT toStartOfHour(timestamp) AS hour, sensor_type,
    count() AS total_readings, uniqExact(sensor_id) AS active_sensors,
    uniqExact(location_id) AS active_locations
FROM sensor_readings GROUP BY hour, sensor_type;
