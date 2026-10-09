-- ============================================================
-- 132_trend_config.sql — Trend analysis configuration
-- ============================================================

CREATE TABLE IF NOT EXISTS trend_monitor_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key VARCHAR(100) NOT NULL UNIQUE,
    location_id UUID,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    min_data_points INTEGER NOT NULL DEFAULT 10,
    time_unit VARCHAR(20) NOT NULL DEFAULT 'day',
    trend_window_days INTEGER NOT NULL DEFAULT 90,
    smoothing_window INTEGER NOT NULL DEFAULT 7,
    smoothing_alpha DOUBLE PRECISION NOT NULL DEFAULT 0.3,
    seasonal_period INTEGER,
    change_point_sensitivity DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    significance_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.05,
    forecast_horizon INTEGER NOT NULL DEFAULT 30,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trend_monitor_config_enabled
    ON trend_monitor_config (is_enabled, metric_key);

CREATE TABLE IF NOT EXISTS smoothing_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key VARCHAR(100) NOT NULL,
    location_id UUID,
    smoothing_type VARCHAR(30) NOT NULL DEFAULT 'exponential'
        CHECK (smoothing_type IN ('moving_average', 'weighted_moving_average',
                                  'exponential', 'holt_linear')),
    window_size INTEGER NOT NULL DEFAULT 7,
    alpha DOUBLE PRECISION NOT NULL DEFAULT 0.3,
    beta DOUBLE PRECISION DEFAULT 0.1,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_smoothing_config_metric
    ON smoothing_config (metric_key, location_id, smoothing_type);
