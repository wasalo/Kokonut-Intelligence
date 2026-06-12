-- ============================================================
-- Schema 011: Sensor Registry, Alert Rules, and Alerts
-- ============================================================

-- Sensor type lookup table
CREATE TABLE IF NOT EXISTS sensor_type (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    unit VARCHAR(50) NOT NULL,
    min_value NUMERIC(12,4),
    max_value NUMERIC(12,4),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed the 7 core sensor types
INSERT INTO sensor_type (name, unit, min_value, max_value, description) VALUES
    ('soil_moisture', '%', 0, 100, 'Volumetric soil water content'),
    ('soil_temperature', '°C', -40, 80, 'Soil temperature at probe depth'),
    ('air_temperature', '°C', -50, 60, 'Ambient air temperature'),
    ('humidity', '%', 0, 100, 'Relative humidity'),
    ('light', 'lux', 0, 200000, 'Ambient light intensity'),
    ('rainfall', 'mm', 0, 500, 'Precipitation accumulation'),
    ('water_level', 'cm', 0, 10000, 'Water level in tank/reservoir/stream')
ON CONFLICT (name) DO NOTHING;

-- Sensor device registry
CREATE TABLE IF NOT EXISTS sensor_device (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    sensor_type_id UUID NOT NULL REFERENCES sensor_type(id),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    manufacturer VARCHAR(255),
    model VARCHAR(255),
    serial_number VARCHAR(255),
    protocol VARCHAR(50), -- http, mqtt, csv, manual
    endpoint_url TEXT,
    status VARCHAR(50) DEFAULT 'active', -- active, inactive, maintenance, decommissioned
    calibration_date DATE,
    calibration_interval_days INTEGER DEFAULT 365,
    installation_date DATE,
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    elevation_m NUMERIC(8,2),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sensor_device_slug ON sensor_device(slug);
CREATE INDEX IF NOT EXISTS idx_sensor_device_location ON sensor_device(location_id);
CREATE INDEX IF NOT EXISTS idx_sensor_device_plot ON sensor_device(plot_id);
CREATE INDEX IF NOT EXISTS idx_sensor_device_type ON sensor_device(sensor_type_id);
CREATE INDEX IF NOT EXISTS idx_sensor_device_status ON sensor_device(status);

-- Ensure sensor readings point at registered devices. Older dev databases may
-- contain slugs in sensor_reading.sensor_id, so translate known slugs first.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'sensor_reading'
          AND column_name = 'sensor_id'
          AND data_type <> 'uuid'
    ) THEN
        UPDATE sensor_reading sr
        SET sensor_id = sd.id::text
        FROM sensor_device sd
        WHERE sr.sensor_id = sd.slug;

        IF NOT EXISTS (
            SELECT 1
            FROM sensor_reading
            WHERE sensor_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        ) THEN
            ALTER TABLE sensor_reading
            ALTER COLUMN sensor_id TYPE UUID USING sensor_id::uuid;
        ELSE
            RAISE NOTICE 'Skipping sensor_reading.sensor_id UUID migration because unmatched non-UUID sensor IDs remain.';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'sensor_reading'
          AND column_name = 'sensor_id'
          AND data_type = 'uuid'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'sensor_reading_sensor_id_fkey'
    ) THEN
        ALTER TABLE sensor_reading
        ADD CONSTRAINT sensor_reading_sensor_id_fkey
        FOREIGN KEY (sensor_id) REFERENCES sensor_device(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- Alert rule configuration
CREATE TABLE IF NOT EXISTS alert_rule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    sensor_type_id UUID NOT NULL REFERENCES sensor_type(id),
    metric VARCHAR(100) NOT NULL, -- value, rate_of_change, gap, min, max
    operator VARCHAR(20) NOT NULL, -- gt, lt, gte, lte, eq, neq, outside_range
    threshold_value NUMERIC(12,4) NOT NULL,
    threshold_value_max NUMERIC(12,4), -- for outside_range operator
    severity VARCHAR(20) DEFAULT 'warning', -- info, warning, critical
    cooldown_minutes INTEGER DEFAULT 60,
    enabled BOOLEAN DEFAULT true,
    auto_create_claim BOOLEAN DEFAULT false,
    claim_type VARCHAR(100), -- sensor_anomaly, threshold_breach, etc.
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_rule_type ON alert_rule(sensor_type_id);
CREATE INDEX IF NOT EXISTS idx_alert_rule_enabled ON alert_rule(enabled);

-- Triggered sensor alerts
CREATE TABLE IF NOT EXISTS sensor_alert (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sensor_device_id UUID NOT NULL REFERENCES sensor_device(id) ON DELETE RESTRICT,
    alert_rule_id UUID NOT NULL REFERENCES alert_rule(id) ON DELETE RESTRICT,
    reading_id UUID REFERENCES sensor_reading(id),
    severity VARCHAR(20) NOT NULL, -- info, warning, critical
    status VARCHAR(50) DEFAULT 'open', -- open, acknowledged, resolved, false_positive
    message TEXT NOT NULL,
    reading_value NUMERIC(12,4),
    threshold_value NUMERIC(12,4),
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID,
    resolved_at TIMESTAMPTZ,
    claim_id UUID, -- links to mrv_claim if auto-created
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sensor_alert_device ON sensor_alert(sensor_device_id);
CREATE INDEX IF NOT EXISTS idx_sensor_alert_status ON sensor_alert(status);
CREATE INDEX IF NOT EXISTS idx_sensor_alert_severity ON sensor_alert(severity);
CREATE INDEX IF NOT EXISTS idx_sensor_alert_triggered ON sensor_alert(triggered_at);

-- Sensor-to-claim workflow (extends existing mrv_claim)
-- Add sensor-specific columns to support sensor data provenance
ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS sensor_device_id UUID REFERENCES sensor_device(id);
ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS sensor_alert_id UUID REFERENCES sensor_alert(id);
ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS source_readings UUID[];
