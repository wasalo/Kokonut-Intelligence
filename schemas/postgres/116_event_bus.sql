-- ============================================================
-- 116_event_bus.sql — Event bus for reactive workflows
-- ============================================================

CREATE TABLE IF NOT EXISTS platform_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    source_table VARCHAR(100),
    source_id UUID,
    payload JSONB NOT NULL DEFAULT '{}',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal'
        CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    worker_id VARCHAR(100),
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    error_message TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_platform_event_status_priority
    ON platform_event (status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_platform_event_type
    ON platform_event (event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_platform_event_created
    ON platform_event (created_at);

CREATE TABLE IF NOT EXISTS event_handler (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    handler_name VARCHAR(100) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    module_path VARCHAR(200) NOT NULL,
    function_name VARCHAR(100) NOT NULL DEFAULT 'handle',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority_order INTEGER NOT NULL DEFAULT 0,
    timeout_seconds INTEGER NOT NULL DEFAULT 30,
    max_concurrency INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_handler_type_enabled
    ON event_handler (event_type, is_enabled);

CREATE TABLE IF NOT EXISTS event_handler_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES platform_event(id) ON DELETE CASCADE,
    handler_id UUID NOT NULL REFERENCES event_handler(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('success', 'error', 'skipped', 'timeout')),
    duration_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_handler_log_event
    ON event_handler_log (event_id);
CREATE INDEX IF NOT EXISTS idx_event_handler_log_handler
    ON event_handler_log (handler_id, created_at);

-- Seed default event types and handlers
INSERT INTO event_handler (handler_name, event_type, module_path, function_name, priority_order) VALUES
    ('anomaly_detector', 'sensor_reading', 'services.ingestion.anomaly_detector', 'handle_sensor_reading', 10),
    ('data_freshness_checker', 'data_stale', 'services.ingestion.data_freshness', 'handle_stale_data', 20),
    ('metric_cache_invalidator', 'metric_computed', 'services.cache.events', 'handle_metric_computed', 5),
    ('crisp_cache_invalidator', 'crisp_scored', 'services.cache.events', 'handle_crisp_scored', 5),
    ('alert_notifier', 'threshold_breached', 'services.events.handlers', 'handle_alert_notification', 1)
ON CONFLICT (handler_name) DO NOTHING;

-- Dead letter table for events that exceed max retries
CREATE TABLE IF NOT EXISTS event_dead_letter (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_event_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    failure_count INTEGER NOT NULL,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMPTZ
);
