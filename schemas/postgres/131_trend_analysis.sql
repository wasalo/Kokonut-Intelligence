-- ============================================================
-- 131_trend_analysis.sql — Trend estimation, smoothing, decomposition
-- ============================================================

CREATE TABLE IF NOT EXISTS trend_estimate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key VARCHAR(100) NOT NULL,
    location_id UUID NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    data_points INTEGER NOT NULL DEFAULT 0,
    slope DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    intercept DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    r_squared DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    standard_error DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    slope_p_value DOUBLE PRECISION,
    direction VARCHAR(20) NOT NULL DEFAULT 'stable'
        CHECK (direction IN ('improving', 'stable', 'declining', 'insufficient_data')),
    confidence_level VARCHAR(20) NOT NULL DEFAULT 'low'
        CHECK (confidence_level IN ('high', 'moderate', 'low', 'insufficient_data')),
    slope_ci_lower DOUBLE PRECISION,
    slope_ci_upper DOUBLE PRECISION,
    time_unit VARCHAR(20) NOT NULL DEFAULT 'day',
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    computed_by VARCHAR(100) NOT NULL DEFAULT 'system',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trend_estimate_metric_location
    ON trend_estimate (metric_key, location_id, computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_trend_estimate_direction
    ON trend_estimate (direction, computed_at DESC);

CREATE TABLE IF NOT EXISTS trend_smoothing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key VARCHAR(100) NOT NULL,
    location_id UUID NOT NULL,
    smoothing_type VARCHAR(30) NOT NULL
        CHECK (smoothing_type IN ('moving_average', 'weighted_moving_average',
                                  'exponential', 'holt_linear')),
    window_size INTEGER,
    alpha DOUBLE PRECISION,
    beta DOUBLE PRECISION,
    original_value DOUBLE PRECISION NOT NULL,
    smoothed_value DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trend_smoothing_metric
    ON trend_smoothing (metric_key, location_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trend_smoothing_type
    ON trend_smoothing (smoothing_type, computed_at DESC);

CREATE TABLE IF NOT EXISTS seasonal_decomposition (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key VARCHAR(100) NOT NULL,
    location_id UUID NOT NULL,
    decomposition_method VARCHAR(30) NOT NULL DEFAULT 'classical'
        CHECK (decomposition_method IN ('classical', 'stl', 'x11')),
    period INTEGER NOT NULL,
    trend_component JSONB NOT NULL DEFAULT '[]',
    seasonal_component JSONB NOT NULL DEFAULT '[]',
    residual_component JSONB NOT NULL DEFAULT '[]',
    seasonal_strength DOUBLE PRECISION,
    trend_strength DOUBLE PRECISION,
    residual_variance DOUBLE PRECISION,
    data_points INTEGER NOT NULL DEFAULT 0,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seasonal_decomposition_metric
    ON seasonal_decomposition (metric_key, location_id, computed_at DESC);

CREATE TABLE IF NOT EXISTS change_point (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key VARCHAR(100) NOT NULL,
    location_id UUID NOT NULL,
    detection_method VARCHAR(30) NOT NULL
        CHECK (detection_method IN ('cusum', 'pelt', 'binary_segmentation', 'window_slider')),
    change_point_index INTEGER NOT NULL,
    change_point_timestamp TIMESTAMPTZ,
    magnitude DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    direction VARCHAR(20) NOT NULL
        CHECK (direction IN ('increase', 'decrease', 'variance_change')),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    pre_mean DOUBLE PRECISION,
    post_mean DOUBLE PRECISION,
    pre_std DOUBLE PRECISION,
    post_std DOUBLE PRECISION,
    segment_count INTEGER NOT NULL DEFAULT 2,
    classification VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'detected'
        CHECK (status IN ('detected', 'confirmed', 'dismissed')),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_change_point_metric
    ON change_point (metric_key, location_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_point_status
    ON change_point (status, confidence DESC);

CREATE TABLE IF NOT EXISTS time_series_forecast (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key VARCHAR(100) NOT NULL,
    location_id UUID NOT NULL,
    model_type VARCHAR(30) NOT NULL DEFAULT 'arima'
        CHECK (model_type IN ('arima', 'exponential_smoothing', 'prophet', 'naive', 'seasonal_naive')),
    model_params JSONB NOT NULL DEFAULT '{}',
    forecast_values JSONB NOT NULL DEFAULT '[]',
    prediction_intervals JSONB NOT NULL DEFAULT '{}',
    forecast_horizon INTEGER NOT NULL,
    time_unit VARCHAR(20) NOT NULL DEFAULT 'day',
    training_points INTEGER NOT NULL DEFAULT 0,
    forecast_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'superseded', 'expired')),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forecast_metric_location
    ON time_series_forecast (metric_key, location_id, forecast_at DESC);
CREATE INDEX IF NOT EXISTS idx_forecast_status
    ON time_series_forecast (status, forecast_at DESC);

CREATE TABLE IF NOT EXISTS forecast_accuracy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id UUID NOT NULL REFERENCES time_series_forecast(id) ON DELETE CASCADE,
    actual_timestamp TIMESTAMPTZ NOT NULL,
    predicted_value DOUBLE PRECISION NOT NULL,
    actual_value DOUBLE PRECISION NOT NULL,
    error_abs DOUBLE PRECISION NOT NULL,
    error_squared DOUBLE PRECISION NOT NULL,
    error_pct DOUBLE PRECISION,
    is_within_ci BOOLEAN,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forecast_accuracy_forecast
    ON forecast_accuracy (forecast_id, actual_timestamp);

CREATE TABLE IF NOT EXISTS trend_dashboard_metric (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key VARCHAR(100) NOT NULL,
    location_id UUID NOT NULL,
    current_value DOUBLE PRECISION,
    trend_slope DOUBLE PRECISION,
    trend_direction VARCHAR(20),
    trend_r_squared DOUBLE PRECISION,
    trend_significance VARCHAR(20),
    seasonal_strength DOUBLE PRECISION,
    noise_level DOUBLE PRECISION,
    change_point_count INTEGER NOT NULL DEFAULT 0,
    last_change_point_at TIMESTAMPTZ,
    forecast_next_value DOUBLE PRECISION,
    forecast_accuracy_mae DOUBLE PRECISION,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trend_dashboard_metric
    ON trend_dashboard_metric (metric_key, location_id, computed_at DESC);
