-- ============================================================
-- 128_adaptive_sampling.sql — Adaptive sensor sampling
-- ============================================================
-- Dynamically adjusts sensor polling intervals based on
-- feedback from the OODA loop: increase when uncertainty is
-- high, decrease when stable to conserve resources.

CREATE TABLE IF NOT EXISTS sampling_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sensor_device_id UUID NOT NULL,
    sensor_type VARCHAR(100) NOT NULL,
    location_id UUID NOT NULL,
    base_interval_minutes INTEGER NOT NULL DEFAULT 15,
    adaptive_interval_minutes INTEGER NOT NULL DEFAULT 15,
    min_interval_minutes INTEGER NOT NULL DEFAULT 1,
    max_interval_minutes INTEGER NOT NULL DEFAULT 60,
    reason TEXT NOT NULL DEFAULT 'initial',
    last_adjusted_at TIMESTAMPTZ,
    adjustment_count INTEGER NOT NULL DEFAULT 0,
    stable_since TIMESTAMPTZ,
    stable_threshold_days INTEGER NOT NULL DEFAULT 7,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sampling_config_sensor
    ON sampling_config (sensor_device_id, sensor_type);
CREATE INDEX IF NOT EXISTS idx_sampling_config_location
    ON sampling_config (location_id);
CREATE INDEX IF NOT EXISTS idx_sampling_config_interval
    ON sampling_config (adaptive_interval_minutes, is_enabled);

CREATE TABLE IF NOT EXISTS sampling_adjustment_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID NOT NULL REFERENCES sampling_config(id) ON DELETE CASCADE,
    previous_interval INTEGER NOT NULL,
    new_interval INTEGER NOT NULL,
    reason VARCHAR(50) NOT NULL
        CHECK (reason IN ('high_uncertainty', 'anomaly_detected', 'feedback_signal',
                          'stable_period', 'manual_override', 'resource_constraint')),
    trigger_source VARCHAR(100),
    trigger_source_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sampling_adjustment_config
    ON sampling_adjustment_log (config_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sampling_adjustment_reason
    ON sampling_adjustment_log (reason, created_at DESC);
