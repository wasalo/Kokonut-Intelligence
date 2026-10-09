-- ============================================================
-- 118_computation_cache.sql — Computation result cache
-- ============================================================
-- Stores pre-computed metric/analytic results with TTL-based
-- invalidation and event-driven cache busting.

CREATE TABLE IF NOT EXISTS cache_entry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key VARCHAR(200) NOT NULL UNIQUE,
    computation_type VARCHAR(100) NOT NULL,
    location_id UUID,
    parameters JSONB NOT NULL DEFAULT '{}',
    result JSONB NOT NULL,
    result_hash VARCHAR(64),
    computed_by VARCHAR(200),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0,
    last_hit_at TIMESTAMPTZ,
    size_bytes INTEGER,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    invalidation_reason TEXT,
    invalidated_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_cache_entry_key
    ON cache_entry (cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_entry_type_location
    ON cache_entry (computation_type, location_id);
CREATE INDEX IF NOT EXISTS idx_cache_entry_expires
    ON cache_entry (expires_at) WHERE is_valid = TRUE;
CREATE INDEX IF NOT EXISTS idx_cache_entry_computed
    ON cache_entry (computed_at DESC);

-- Invalidation rules — defines which event types invalidate which cache types
CREATE TABLE IF NOT EXISTS cache_invalidation_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    target_computation_type VARCHAR(100) NOT NULL,
    scope VARCHAR(50) NOT NULL DEFAULT 'location'
        CHECK (scope IN ('global', 'location', 'specific')),
    description TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default invalidation rules
INSERT INTO cache_invalidation_rule (event_type, target_computation_type, scope, description) VALUES
    ('sensor_reading', 'metric', 'location', 'Invalidate metrics when new sensor data arrives'),
    ('sensor_reading', 'anomaly_score', 'location', 'Invalidate anomaly scores when new sensor data arrives'),
    ('metric_computed', 'analytics', 'location', 'Invalidate analytics when metrics change'),
    ('harvest_recorded', 'metric', 'location', 'Invalidate metrics when harvest is recorded'),
    ('farm_activity_logged', 'metric', 'location', 'Invalidate metrics when farm activity changes'),
    ('weather_update', 'metric', 'location', 'Invalidate metrics when weather data arrives'),
    ('crisp_scored', 'crisp', 'location', 'Invalidate CRISP scores when re-scored'),
    ('soil_measurement', 'metric', 'location', 'Invalidate metrics when soil data changes')
ON CONFLICT DO NOTHING;
