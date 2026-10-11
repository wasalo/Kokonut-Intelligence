-- ISOLATED REHEARSAL ONLY. Quiesce all raw inserts and ensure both v2 targets
-- are empty first. This is deliberately not part of automatic schema bootstrap.
INSERT INTO mv_daily_sensor_summary_v2
SELECT toDate(timestamp), location_id, sensor_type,
 avgState(value), minState(value), maxState(value), countState(),
 uniqExactState(sensor_id), sumState(toUInt64(quality != 'good'))
FROM sensor_readings GROUP BY toDate(timestamp), location_id, sensor_type;
INSERT INTO mv_sensor_reading_rate_v2
SELECT toStartOfHour(timestamp), sensor_type, countState(),
 uniqExactState(sensor_id), uniqExactState(location_id)
FROM sensor_readings GROUP BY toStartOfHour(timestamp), sensor_type;
