-- Eagle View: Sensor & Alert Status
-- Active sensors, recent readings, and alert summary

SELECT
  st.name as sensor_type,
  COUNT(DISTINCT sd.id) as device_count,
  COUNT(DISTINCT sr.id) as total_readings,
  COALESCE(AVG(sr.value), 0) as avg_value,
  COALESCE(MIN(sr.value), 0) as min_value,
  COALESCE(MAX(sr.value), 0) as max_value,
  COUNT(DISTINCT sa.id) as total_alerts,
  COUNT(CASE WHEN sa.severity = 'critical' THEN 1 END) as critical_alerts,
  COUNT(CASE WHEN sa.severity = 'warning' THEN 1 END) as warning_alerts,
  MAX(sr.reading_time) as latest_reading
FROM sensor_type st
LEFT JOIN sensor_device sd ON st.id = sd.sensor_type_id AND sd.status = 'active'
LEFT JOIN sensor_reading sr ON sd.id = sr.sensor_id
LEFT JOIN sensor_alert sa ON sr.id = sa.reading_id
GROUP BY st.name
ORDER BY device_count DESC;
