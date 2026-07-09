-- ============================================================
-- 077_telemetry_infrastructure.sql — Freshness monitoring,
-- remote sensing automation, and device health tracking
-- ============================================================

-- 1. Data freshness configuration (SLAs per source)
CREATE TABLE IF NOT EXISTS data_freshness_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_system VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    expected_interval_minutes INTEGER NOT NULL CHECK (expected_interval_minutes > 0),
    stale_threshold_minutes INTEGER NOT NULL CHECK (stale_threshold_minutes > 0),
    critical_threshold_minutes INTEGER NOT NULL CHECK (critical_threshold_minutes > 0),
    location_scoped BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE data_freshness_config DROP CONSTRAINT IF EXISTS chk_freshness_thresholds;
ALTER TABLE data_freshness_config ADD CONSTRAINT chk_freshness_thresholds CHECK (
    stale_threshold_minutes <= critical_threshold_minutes
);

-- 2. Data freshness check results
CREATE TABLE IF NOT EXISTS data_freshness_check (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_id UUID NOT NULL REFERENCES data_freshness_config(id) ON DELETE CASCADE,
    source_system VARCHAR(100) NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    last_data_at TIMESTAMPTZ,
    check_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    gap_minutes INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'fresh',
    alert_sent BOOLEAN DEFAULT FALSE,
    alert_channel VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_freshness_check_config ON data_freshness_check(config_id);
CREATE INDEX IF NOT EXISTS idx_freshness_check_source ON data_freshness_check(source_system);
CREATE INDEX IF NOT EXISTS idx_freshness_check_status ON data_freshness_check(status);
CREATE INDEX IF NOT EXISTS idx_freshness_check_time ON data_freshness_check(check_time);

ALTER TABLE data_freshness_check DROP CONSTRAINT IF EXISTS chk_freshness_status;
ALTER TABLE data_freshness_check ADD CONSTRAINT chk_freshness_status CHECK (
    status IN ('fresh', 'stale', 'critical', 'no_data', 'error')
);

-- 3. Remote sensing automated fetch jobs
CREATE TABLE IF NOT EXISTS remote_sensing_job (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'gee',
    bbox GEOMETRY(POLYGON, 4326),
    start_date DATE,
    end_date DATE,
    cloud_max_pct NUMERIC(5,2) DEFAULT 20.0,
    cadence_days INTEGER DEFAULT 7 CHECK (cadence_days > 0),
    status VARCHAR(50) DEFAULT 'active',
    last_run_at TIMESTAMPTZ,
    last_run_status VARCHAR(50),
    next_run_at TIMESTAMPTZ,
    observations_fetched INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rs_job_location ON remote_sensing_job(location_id);
CREATE INDEX IF NOT EXISTS idx_rs_job_status ON remote_sensing_job(status);
CREATE INDEX IF NOT EXISTS idx_rs_job_next_run ON remote_sensing_job(next_run_at);

ALTER TABLE remote_sensing_job DROP CONSTRAINT IF EXISTS chk_rs_job_provider;
ALTER TABLE remote_sensing_job ADD CONSTRAINT chk_rs_job_provider CHECK (provider IN ('gee', 'copernicus', 'manual'));

ALTER TABLE remote_sensing_job DROP CONSTRAINT IF EXISTS chk_rs_job_status;
ALTER TABLE remote_sensing_job ADD CONSTRAINT chk_rs_job_status CHECK (status IN ('active', 'paused', 'completed', 'error'));

-- 4. Sensor device health tracking
CREATE TABLE IF NOT EXISTS sensor_device_health (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id UUID NOT NULL REFERENCES sensor_device(id) ON DELETE CASCADE,
    last_seen_at TIMESTAMPTZ,
    battery_pct NUMERIC(5,2) CHECK (battery_pct IS NULL OR (battery_pct >= 0 AND battery_pct <= 100)),
    signal_strength_dbm NUMERIC(8,2),
    firmware_version VARCHAR(100),
    uptime_hours NUMERIC(10,2),
    reading_rate_per_hour NUMERIC(8,2),
    status VARCHAR(20) DEFAULT 'unknown',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(device_id)
);

CREATE INDEX IF NOT EXISTS idx_device_health_device ON sensor_device_health(device_id);
CREATE INDEX IF NOT EXISTS idx_device_health_status ON sensor_device_health(status);

ALTER TABLE sensor_device_health DROP CONSTRAINT IF EXISTS chk_device_health_status;
ALTER TABLE sensor_device_health ADD CONSTRAINT chk_device_health_status CHECK (
    status IN ('online', 'offline', 'degraded', 'unknown')
);

-- 5. Freshness summary view
CREATE OR REPLACE VIEW v_data_freshness_summary AS
SELECT
    dfc.source_system,
    dfc.description,
    dfc.expected_interval_minutes,
    dfc.stale_threshold_minutes,
    dfc.critical_threshold_minutes,
    dfc.is_active,
    (SELECT MAX(dfc2.last_data_at)
     FROM data_freshness_check dfc2
     WHERE dfc2.source_system = dfc.source_system
     AND dfc2.status != 'error') AS latest_data_at,
    (SELECT dfc2.status
     FROM data_freshness_check dfc2
     WHERE dfc2.source_system = dfc.source_system
     ORDER BY dfc2.check_time DESC
     LIMIT 1) AS current_status,
    (SELECT dfc2.gap_minutes
     FROM data_freshness_check dfc2
     WHERE dfc2.source_system = dfc.source_system
     ORDER BY dfc2.check_time DESC
     LIMIT 1) AS current_gap_minutes,
    (SELECT COUNT(*)
     FROM data_freshness_check dfc2
     WHERE dfc2.source_system = dfc.source_system
     AND dfc2.status = 'critical'
     AND dfc2.check_time >= NOW() - INTERVAL '24 hours') AS critical_alerts_24h
FROM data_freshness_config dfc
WHERE dfc.is_active = TRUE
ORDER BY dfc.source_system;

-- 6. Sensor device health summary view
CREATE OR REPLACE VIEW v_sensor_device_health_summary AS
SELECT
    sd.id AS device_id,
    sd.name AS device_name,
    sd.slug AS device_slug,
    sd.status AS device_status,
    sd.protocol,
    st.name AS sensor_type,
    sdh.last_seen_at,
    sdh.battery_pct,
    sdh.signal_strength_dbm,
    sdh.firmware_version,
    sdh.reading_rate_per_hour,
    sdh.status AS health_status,
    CASE
        WHEN sdh.last_seen_at IS NULL THEN 'never_seen'
        WHEN sdh.last_seen_at >= NOW() - INTERVAL '1 hour' THEN 'online'
        WHEN sdh.last_seen_at >= NOW() - INTERVAL '24 hours' THEN 'stale'
        ELSE 'offline'
    END AS connectivity_status,
    EXTRACT(EPOCH FROM (NOW() - sdh.last_seen_at)) / 3600 AS hours_since_last_seen
FROM sensor_device sd
JOIN sensor_type st ON st.id = sd.sensor_type_id
LEFT JOIN sensor_device_health sdh ON sdh.device_id = sd.id
WHERE sd.status = 'active'
ORDER BY sdh.last_seen_at DESC NULLS LAST;
