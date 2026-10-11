-- Versioned sensor rollups; legacy views remain available for rollback.
-- No POPULATE: existing raw rows require an explicit quiesced, one-time backfill.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_sensor_summary_v2
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (day, location_id, sensor_type)
AS SELECT
    toDate(timestamp) AS day, location_id, sensor_type,
    avgState(value) AS avg_value_state,
    minState(value) AS min_value_state,
    maxState(value) AS max_value_state,
    countState() AS total_readings_state,
    uniqExactState(sensor_id) AS active_sensors_state,
    sumState(toUInt64(quality != 'good')) AS suspect_readings_state
FROM sensor_readings
GROUP BY day, location_id, sensor_type;

CREATE VIEW IF NOT EXISTS v_daily_sensor_summary_v2 AS
SELECT day, location_id, sensor_type,
    avgMerge(avg_value_state) AS avg_value,
    minMerge(min_value_state) AS min_value,
    maxMerge(max_value_state) AS max_value,
    countMerge(total_readings_state) AS total_readings,
    uniqExactMerge(active_sensors_state) AS active_sensors,
    sumMerge(suspect_readings_state) AS suspect_readings
FROM mv_daily_sensor_summary_v2
GROUP BY day, location_id, sensor_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sensor_reading_rate_v2
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, sensor_type)
AS SELECT
    toStartOfHour(timestamp) AS hour, sensor_type,
    countState() AS total_readings_state,
    uniqExactState(sensor_id) AS active_sensors_state,
    uniqExactState(location_id) AS active_locations_state
FROM sensor_readings
GROUP BY hour, sensor_type;

CREATE VIEW IF NOT EXISTS v_sensor_reading_rate_v2 AS
SELECT hour, sensor_type,
    countMerge(total_readings_state) AS total_readings,
    uniqExactMerge(active_sensors_state) AS active_sensors,
    uniqExactMerge(active_locations_state) AS active_locations
FROM mv_sensor_reading_rate_v2
GROUP BY hour, sensor_type;
