-- ============================================================
-- 297_event_handler_registration_fix.sql - Repair event handler paths
-- ============================================================

-- Keep the original handler names and event contracts, but point them at
-- callable implementations. This also repairs databases where 116 was
-- already applied before the registration paths were corrected.
UPDATE event_handler
SET module_path = 'services.ingestion.anomaly_detector',
    function_name = 'handle_sensor_reading',
    updated_at = NOW()
WHERE handler_name = 'anomaly_detector';

UPDATE event_handler
SET module_path = 'services.events.handlers',
    function_name = 'handle_stale_data',
    updated_at = NOW()
WHERE handler_name = 'data_freshness_checker';
