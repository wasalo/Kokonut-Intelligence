-- ============================================================
-- 050_scheduled_tasks.sql — Migrate crontab to scheduled_task table
-- ============================================================
-- These entries mirror config/worker/crontab so the database-driven
-- task scheduler can replace the static crontab.

INSERT INTO scheduled_task (name, module_path, command_args, cron_expression, priority, timeout_seconds, max_retries, is_enabled) VALUES
    -- Weather ingestion — every 6 hours
    ('weather_ingestion', 'services.ingestion.weather', '[]', '0 */6 * * *', 'normal', 600, 3, TRUE),

    -- Market data — daily at 06:00 UTC
    ('market_data_world_bank', 'services.ingestion.market_data', '["--source", "world_bank"]', '0 6 * * *', 'normal', 900, 3, TRUE),

    -- EAS indexer — every 15 minutes
    ('eas_indexer', 'services.ingestion.eas_indexer', '[]', '*/15 * * * *', 'high', 300, 5, TRUE),

    -- RPC wallet indexer — every 30 minutes
    ('rpc_indexer', 'services.ingestion.rpc_indexer', '[]', '*/30 * * * *', 'high', 300, 5, TRUE),

    -- Sensor ingester — every 5 minutes
    ('sensor_ingester', 'services.ingestion.sensor_ingester', '[]', '*/5 * * * *', 'high', 120, 3, TRUE),

    -- Gnosis Chain indexer — every 2 hours
    ('gnosis_indexer', 'services.ingestion.gnosis_indexer', '[]', '0 */2 * * *', 'normal', 600, 3, TRUE),

    -- Anomaly detection — every hour
    ('anomaly_detection', 'services.ingestion.anomaly_detector', '[]', '0 * * * *', 'normal', 600, 3, TRUE),

    -- Metrics computation — every 4 hours (draft values for independent review)
    ('metrics_computation', 'services.metrics', '["--compute", "--all-locations"]', '0 */4 * * *', 'normal', 1800, 3, TRUE),

    -- Data freshness check — every hour
    ('data_freshness_check', 'services.ingestion.data_freshness', '["--check"]', '0 * * * *', 'normal', 300, 2, TRUE),

    -- Dashboard dataset refresh — every 6 hours
    ('dashboard_dataset_refresh', 'services.export.dataset_refresh', '["--all"]', '0 */6 * * *', 'normal', 900, 3, TRUE),

    -- Climate data refresh — weekly (Sundays at 03:00 UTC)
    ('climate_data_refresh', 'services.ingestion.climate_data', '["--all"]', '0 3 * * 0', 'low', 3600, 2, TRUE),

    -- Event bus processing — every 2 minutes
    ('event_bus_process', 'services.events', '["--process"]', '*/2 * * * *', 'high', 120, 3, TRUE),

    -- Event cleanup — daily at 04:00 UTC
    ('event_cleanup', 'services.events', '["--cleanup"]', '0 4 * * *', 'low', 300, 1, TRUE)
ON CONFLICT (name) DO UPDATE SET
    module_path = EXCLUDED.module_path,
    command_args = EXCLUDED.command_args,
    cron_expression = EXCLUDED.cron_expression,
    priority = EXCLUDED.priority,
    timeout_seconds = EXCLUDED.timeout_seconds,
    max_retries = EXCLUDED.max_retries,
    is_enabled = EXCLUDED.is_enabled,
    updated_at = NOW();
