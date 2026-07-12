-- ============================================================
-- 120_stream_processor.sql — Real-time stream processing
-- ============================================================

CREATE TABLE IF NOT EXISTS stream_window (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sensor_device_id UUID NOT NULL,
    metric VARCHAR(100) NOT NULL,
    window_size VARCHAR(20) NOT NULL
        CHECK (window_size IN ('1min', '5min', '15min', '1hour')),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    avg_value DOUBLE PRECISION,
    sample_count INTEGER DEFAULT 0,
    anomaly_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stream_window_sensor_metric
    ON stream_window (sensor_device_id, metric, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_stream_window_time
    ON stream_window (window_start DESC);

CREATE TABLE IF NOT EXISTS stream_buffer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sensor_device_id UUID NOT NULL,
    metric VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(20),
    quality INTEGER DEFAULT 100,
    timestamp TIMESTAMPTZ NOT NULL,
    ingested BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stream_buffer_pending
    ON stream_buffer (created_at) WHERE NOT ingested;
CREATE INDEX IF NOT EXISTS idx_stream_buffer_sensor
    ON stream_buffer (sensor_device_id, metric, timestamp DESC);

CREATE TABLE IF NOT EXISTS stream_alert (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sensor_device_id UUID NOT NULL,
    alert_type VARCHAR(50) NOT NULL
        CHECK (alert_type IN ('threshold', 'anomaly', 'gap', 'spike', 'rate_of_change')),
    severity VARCHAR(20) NOT NULL
        CHECK (severity IN ('critical', 'warning', 'info')),
    metric VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    message TEXT,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stream_alert_unacked
    ON stream_alert (created_at DESC) WHERE NOT acknowledged;
CREATE INDEX IF NOT EXISTS idx_stream_alert_sensor
    ON stream_alert (sensor_device_id, metric, created_at DESC);
