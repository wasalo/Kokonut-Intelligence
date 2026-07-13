-- 146_precision_irrigation.sql
-- Precision Irrigation Automation: zones, moisture targets, schedules,
-- events, automation rules, and water-use efficiency tracking.
-- Precision Agriculture Phase 5: Irrigation Automation

BEGIN;

-- ============================================================
-- IRRIGATION ZONES
-- ============================================================

CREATE TABLE IF NOT EXISTS irrigation_zone (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    zone_code VARCHAR(50),
    soil_type VARCHAR(100),
    crop_id UUID REFERENCES crop(id),
    area_m2 NUMERIC(12,4),
    depth_cm NUMERIC(6,1) DEFAULT 30,
    field_capacity_pct NUMERIC(5,2),
    wilting_point_pct NUMERIC(5,2),
    bulk_density NUMERIC(4,2),
    sensor_device_id UUID REFERENCES sensor_device(id),
    actuator_device_id UUID,
    geometry GEOMETRY(POLYGON, 4326),
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'maintenance')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_irrigation_zone_location ON irrigation_zone(location_id, status);
CREATE INDEX IF NOT EXISTS idx_irrigation_zone_plot ON irrigation_zone(plot_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_zone_geom ON irrigation_zone USING GIST(geometry);

-- ============================================================
-- SOIL MOISTURE TARGETS
-- ============================================================

CREATE TABLE IF NOT EXISTS soil_moisture_target (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id UUID NOT NULL REFERENCES irrigation_zone(id) ON DELETE CASCADE,
    crop_id UUID REFERENCES crop(id),
    growth_stage VARCHAR(100),
    target_min_pct NUMERIC(5,2) NOT NULL,
    target_max_pct NUMERIC(5,2) NOT NULL,
    stress_threshold_pct NUMERIC(5,2),
    irrigation_trigger_pct NUMERIC(5,2) NOT NULL,
    refill_to_pct NUMERIC(5,2) NOT NULL,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(zone_id, crop_id, growth_stage)
);

CREATE INDEX IF NOT EXISTS idx_soil_moisture_target_zone ON soil_moisture_target(zone_id);

-- ============================================================
-- IRRIGATION SCHEDULES
-- ============================================================

CREATE TABLE IF NOT EXISTS irrigation_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id UUID NOT NULL REFERENCES irrigation_zone(id) ON DELETE CASCADE,
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ,
    planned_duration_min INTEGER,
    planned_volume_l NUMERIC(10,2),
    reason VARCHAR(255),
    etc_mm NUMERIC(8,4),
    rainfall_forecast_mm NUMERIC(8,4) DEFAULT 0,
    current_soil_moisture_pct NUMERIC(5,2),
    target_soil_moisture_pct NUMERIC(5,2),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN (
        'pending', 'approved', 'running', 'completed', 'cancelled', 'failed'
    )),
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    triggered_by VARCHAR(50) CHECK (triggered_by IN ('manual', 'scheduled', 'automation', 'advisory')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_irrigation_schedule_zone ON irrigation_schedule(zone_id, scheduled_start);
CREATE INDEX IF NOT EXISTS idx_irrigation_schedule_status ON irrigation_schedule(status, scheduled_start);
CREATE INDEX IF NOT EXISTS idx_irrigation_schedule_pending ON irrigation_schedule(status, scheduled_start)
    WHERE status = 'pending';

-- ============================================================
-- IRRIGATION EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS irrigation_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID REFERENCES irrigation_schedule(id) ON DELETE SET NULL,
    zone_id UUID NOT NULL REFERENCES irrigation_zone(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_min NUMERIC(8,2),
    volume_l NUMERIC(10,2),
    flow_rate_lpm NUMERIC(8,2),
    soil_moisture_before_pct NUMERIC(5,2),
    soil_moisture_after_pct NUMERIC(5,2),
    etc_mm NUMERIC(8,4),
    water_source VARCHAR(100),
    method VARCHAR(50) CHECK (method IN ('drip', 'sprinkler', 'flood', 'pivot', 'manual')),
    trigger_type VARCHAR(50) CHECK (trigger_type IN ('manual', 'scheduled', 'automation', 'advisory')),
    efficiency_pct NUMERIC(5,2),
    run_off_pct NUMERIC(5,2) DEFAULT 0,
    deep_percolation_pct NUMERIC(5,2) DEFAULT 0,
    energy_cost_usd NUMERIC(8,4),
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_irrigation_event_zone ON irrigation_event(zone_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_irrigation_event_schedule ON irrigation_event(schedule_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_event_started ON irrigation_event(started_at DESC);

-- ============================================================
-- AUTOMATION RULES
-- ============================================================

CREATE TABLE IF NOT EXISTS automation_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES irrigation_zone(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sensor_metric VARCHAR(100) NOT NULL,
    operator VARCHAR(20) NOT NULL CHECK (operator IN ('lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between')),
    threshold_low NUMERIC(10,4) NOT NULL,
    threshold_high NUMERIC(10,4),
    unit VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL DEFAULT 'irrigate',
    action_params JSONB DEFAULT '{}',
    min_duration_min INTEGER DEFAULT 0,
    cooldown_min INTEGER DEFAULT 60,
    max_per_day INTEGER DEFAULT 5,
    time_window_start TIME,
    time_window_end TIME,
    requires_approval BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'disabled', 'archived')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_automation_rule_location ON automation_rule(location_id, status);
CREATE INDEX IF NOT EXISTS idx_automation_rule_zone ON automation_rule(zone_id, status);
CREATE INDEX IF NOT EXISTS idx_automation_rule_active ON automation_rule(status) WHERE status = 'active';

-- ============================================================
-- WATER EFFICIENCY LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS water_efficiency_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES irrigation_event(id) ON DELETE CASCADE,
    zone_id UUID NOT NULL REFERENCES irrigation_zone(id) ON DELETE CASCADE,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    volume_l NUMERIC(10,2) NOT NULL,
    crop_water_need_l NUMERIC(10,2),
    effective_volume_l NUMERIC(10,2),
    distribution_uniformity NUMERIC(5,2),
    application_efficiency_pct NUMERIC(5,2),
    water_productivity_kg_m3 NUMERIC(8,4),
    yield_kg NUMERIC(10,2),
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_water_efficiency_zone ON water_efficiency_log(zone_id, logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_water_efficiency_event ON water_efficiency_log(event_id);

-- ============================================================
-- VIEWS
-- ============================================================

-- Current zone status with latest soil moisture and next pending schedule
CREATE OR REPLACE VIEW v_irrigation_status AS
SELECT
    iz.id AS zone_id,
    iz.location_id,
    l.name AS location_name,
    iz.name AS zone_name,
    iz.zone_code,
    iz.soil_type,
    c.name AS crop_name,
    iz.area_m2,
    iz.status AS zone_status,
    sm.target_min_pct,
    sm.target_max_pct,
    sm.irrigation_trigger_pct,
    sm.refill_to_pct,
    last_read.reading_value AS current_soil_moisture_pct,
    last_read.reading_time AS last_moisture_reading,
    CASE
        WHEN last_read.reading_value IS NULL THEN 'no_data'
        WHEN last_read.reading_value < sm.irrigation_trigger_pct THEN 'below_trigger'
        WHEN last_read.reading_value < sm.target_min_pct THEN 'below_target'
        WHEN last_read.reading_value BETWEEN sm.target_min_pct AND sm.target_max_pct THEN 'in_range'
        ELSE 'above_target'
    END AS moisture_status,
    next_sch.scheduled_start AS next_irrigation_start,
    next_sch.planned_volume_l AS next_irrigation_volume_l,
    next_sch.status AS next_irrigation_status,
    last_event.started_at AS last_irrigation_at,
    last_event.volume_l AS last_irrigation_volume_l
FROM irrigation_zone iz
JOIN location l ON l.id = iz.location_id
LEFT JOIN crop c ON c.id = iz.crop_id
LEFT JOIN LATERAL (
    SELECT target_min_pct, target_max_pct, irrigation_trigger_pct, refill_to_pct
    FROM soil_moisture_target
    WHERE zone_id = iz.id
    ORDER BY created_at DESC LIMIT 1
) sm ON TRUE
LEFT JOIN LATERAL (
    SELECT sr.reading_value, sr.reading_time
    FROM sensor_reading sr
    WHERE sr.sensor_id = iz.sensor_device_id
      AND sr.sensor_type = 'soil_moisture'
    ORDER BY sr.reading_time DESC LIMIT 1
) last_read ON TRUE
LEFT JOIN LATERAL (
    SELECT scheduled_start, planned_volume_l, status
    FROM irrigation_schedule
    WHERE zone_id = iz.id AND status = 'pending'
    ORDER BY scheduled_start ASC LIMIT 1
) next_sch ON TRUE
LEFT JOIN LATERAL (
    SELECT started_at, volume_l
    FROM irrigation_event
    WHERE zone_id = iz.id
    ORDER BY started_at DESC LIMIT 1
) last_event ON TRUE
WHERE iz.status = 'active';

-- Water use efficiency trends by zone
CREATE OR REPLACE VIEW v_water_efficiency AS
SELECT
    wlog.zone_id,
    iz.name AS zone_name,
    iz.location_id,
    l.name AS location_name,
    c.name AS crop_name,
    DATE_TRUNC('week', wlog.logged_at) AS week,
    COUNT(*) AS event_count,
    SUM(wlog.volume_l) AS total_volume_l,
    AVG(wlog.volume_l) AS avg_volume_l,
    AVG(wlog.application_efficiency_pct) AS avg_application_efficiency_pct,
    AVG(wlog.distribution_uniformity) AS avg_distribution_uniformity,
    AVG(wlog.water_productivity_kg_m3) AS avg_water_productivity,
    SUM(wlog.yield_kg) AS total_yield_kg,
    CASE
        WHEN SUM(wlog.effective_volume_l) > 0
        THEN ROUND((SUM(wlog.yield_kg) / SUM(wlog.effective_volume_l) * 1000)::numeric, 2)
        ELSE NULL
    END AS actual_water_productivity_g_l
FROM water_efficiency_log wlog
JOIN irrigation_zone iz ON iz.id = wlog.zone_id
JOIN location l ON l.id = iz.location_id
LEFT JOIN crop c ON c.id = iz.crop_id
GROUP BY wlog.zone_id, iz.name, iz.location_id, l.name, c.name, DATE_TRUNC('week', wlog.logged_at)
ORDER BY wlog.zone_id, week DESC;

-- Active automation rules
CREATE OR REPLACE VIEW v_automation_rules AS
SELECT
    ar.id AS rule_id,
    ar.location_id,
    l.name AS location_name,
    ar.zone_id,
    iz.name AS zone_name,
    ar.name AS rule_name,
    ar.description,
    ar.sensor_metric,
    ar.operator,
    ar.threshold_low,
    ar.threshold_high,
    ar.unit,
    ar.action,
    ar.action_params,
    ar.min_duration_min,
    ar.cooldown_min,
    ar.max_per_day,
    ar.time_window_start,
    ar.time_window_end,
    ar.requires_approval,
    ar.priority,
    ar.status,
    ar.created_at
FROM automation_rule ar
JOIN location l ON l.id = ar.location_id
LEFT JOIN irrigation_zone iz ON iz.id = ar.zone_id
WHERE ar.status = 'active'
ORDER BY ar.priority DESC, ar.created_at DESC;

COMMIT;

-- ============================================================
-- SEED: Default soil moisture targets by crop and growth stage
-- Based on FAO irrigation guidelines (percent volumetric water content)
-- ============================================================

INSERT INTO irrigation_zone (id, location_id, name, status)
SELECT gen_random_uuid(), id, 'Default Zone', 'active'
FROM location
WHERE slug = 'adelphi'
  AND NOT EXISTS (
      SELECT 1 FROM irrigation_zone WHERE location_id = location.id
  );

-- Maize targets
INSERT INTO soil_moisture_target (zone_id, crop_id, growth_stage, target_min_pct, target_max_pct, stress_threshold_pct, irrigation_trigger_pct, refill_to_pct)
SELECT
    iz.id,
    c.id,
    v.stage,
    v.target_min,
    v.target_max,
    v.stress_threshold,
    v.trigger_pct,
    v.refill_pct
FROM irrigation_zone iz
CROSS JOIN crop c
CROSS JOIN (VALUES
    ('germination', 55, 70, 40, 45, 70),
    ('vegetative', 50, 65, 35, 40, 65),
    ('flowering', 60, 75, 45, 50, 75),
    ('grain_fill', 50, 65, 35, 40, 65),
    ('maturity', 40, 55, 30, 35, 55)
) AS v(stage, target_min, target_max, stress_threshold, trigger_pct, refill_pct)
WHERE c.name = 'maize'
  AND iz.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM soil_moisture_target smt
      WHERE smt.zone_id = iz.id AND smt.crop_id = c.id AND smt.growth_stage = v.stage
  );

-- Beans targets
INSERT INTO soil_moisture_target (zone_id, crop_id, growth_stage, target_min_pct, target_max_pct, stress_threshold_pct, irrigation_trigger_pct, refill_to_pct)
SELECT
    iz.id,
    c.id,
    v.stage,
    v.target_min,
    v.target_max,
    v.stress_threshold,
    v.trigger_pct,
    v.refill_pct
FROM irrigation_zone iz
CROSS JOIN crop c
CROSS JOIN (VALUES
    ('germination', 55, 70, 40, 45, 70),
    ('vegetative', 50, 65, 35, 40, 65),
    ('flowering', 55, 70, 40, 45, 70),
    ('pod_fill', 45, 60, 30, 35, 60),
    ('maturity', 35, 50, 25, 30, 50)
) AS v(stage, target_min, target_max, stress_threshold, trigger_pct, refill_pct)
WHERE c.name = 'beans'
  AND iz.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM soil_moisture_target smt
      WHERE smt.zone_id = iz.id AND smt.crop_id = c.id AND smt.growth_stage = v.stage
  );

-- Cassava targets
INSERT INTO soil_moisture_target (zone_id, crop_id, growth_stage, target_min_pct, target_max_pct, stress_threshold_pct, irrigation_trigger_pct, refill_to_pct)
SELECT
    iz.id,
    c.id,
    v.stage,
    v.target_min,
    v.target_max,
    v.stress_threshold,
    v.trigger_pct,
    v.refill_pct
FROM irrigation_zone iz
CROSS JOIN crop c
CROSS JOIN (VALUES
    ('establishment', 50, 65, 35, 40, 65),
    ('vegetative', 45, 60, 30, 35, 60),
    ('tuber_initiation', 50, 65, 35, 40, 65),
    ('bulking', 45, 60, 30, 35, 60),
    ('maturity', 35, 50, 25, 30, 50)
) AS v(stage, target_min, target_max, stress_threshold, trigger_pct, refill_pct)
WHERE c.name = 'cassava'
  AND iz.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM soil_moisture_target smt
      WHERE smt.zone_id = iz.id AND smt.crop_id = c.id AND smt.growth_stage = v.stage
  );

-- Coffee targets
INSERT INTO soil_moisture_target (zone_id, crop_id, growth_stage, target_min_pct, target_max_pct, stress_threshold_pct, irrigation_trigger_pct, refill_to_pct)
SELECT
    iz.id,
    c.id,
    v.stage,
    v.target_min,
    v.target_max,
    v.stress_threshold,
    v.trigger_pct,
    v.refill_pct
FROM irrigation_zone iz
CROSS JOIN crop c
CROSS JOIN (VALUES
    ('flowering', 55, 70, 40, 45, 70),
    ('pinhead', 60, 75, 45, 50, 75),
    ('cherry_development', 50, 65, 35, 40, 65),
    ('harvest', 45, 60, 30, 35, 60),
    ('dormancy', 40, 55, 25, 30, 55)
) AS v(stage, target_min, target_max, stress_threshold, trigger_pct, refill_pct)
WHERE c.name = 'coffee'
  AND iz.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM soil_moisture_target smt
      WHERE smt.zone_id = iz.id AND smt.crop_id = c.id AND smt.growth_stage = v.stage
  );

-- Avocado targets
INSERT INTO soil_moisture_target (zone_id, crop_id, growth_stage, target_min_pct, target_max_pct, stress_threshold_pct, irrigation_trigger_pct, refill_to_pct)
SELECT
    iz.id,
    c.id,
    v.stage,
    v.target_min,
    v.target_max,
    v.stress_threshold,
    v.trigger_pct,
    v.refill_pct
FROM irrigation_zone iz
CROSS JOIN crop c
CROSS JOIN (VALUES
    ('flowering', 55, 70, 40, 45, 70),
    ('fruit_set', 60, 75, 45, 50, 75),
    ('fruit_development', 50, 65, 35, 40, 65),
    ('harvest', 45, 60, 30, 35, 60),
    ('vegetative_flush', 50, 65, 35, 40, 65)
) AS v(stage, target_min, target_max, stress_threshold, trigger_pct, refill_pct)
WHERE c.name = 'avocado'
  AND iz.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM soil_moisture_target smt
      WHERE smt.zone_id = iz.id AND smt.crop_id = c.id AND smt.growth_stage = v.stage
  );

-- Tomato targets
INSERT INTO soil_moisture_target (zone_id, crop_id, growth_stage, target_min_pct, target_max_pct, stress_threshold_pct, irrigation_trigger_pct, refill_to_pct)
SELECT
    iz.id,
    c.id,
    v.stage,
    v.target_min,
    v.target_max,
    v.stress_threshold,
    v.trigger_pct,
    v.refill_pct
FROM irrigation_zone iz
CROSS JOIN crop c
CROSS JOIN (VALUES
    ('transplant', 55, 70, 40, 45, 70),
    ('vegetative', 55, 70, 40, 45, 70),
    ('flowering', 60, 75, 45, 50, 75),
    ('fruiting', 55, 70, 40, 45, 70),
    ('ripening', 45, 60, 30, 35, 60)
) AS v(stage, target_min, target_max, stress_threshold, trigger_pct, refill_pct)
WHERE c.name = 'tomato'
  AND iz.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM soil_moisture_target smt
      WHERE smt.zone_id = iz.id AND smt.crop_id = c.id AND smt.growth_stage = v.stage
  );

-- Sweet potato targets
INSERT INTO soil_moisture_target (zone_id, crop_id, growth_stage, target_min_pct, target_max_pct, stress_threshold_pct, irrigation_trigger_pct, refill_to_pct)
SELECT
    iz.id,
    c.id,
    v.stage,
    v.target_min,
    v.target_max,
    v.stress_threshold,
    v.trigger_pct,
    v.refill_pct
FROM irrigation_zone iz
CROSS JOIN crop c
CROSS JOIN (VALUES
    ('establishment', 50, 65, 35, 40, 65),
    ('vegetative', 45, 60, 30, 35, 60),
    ('tuber_init', 50, 65, 35, 40, 65),
    ('bulking', 45, 60, 30, 35, 60),
    ('maturity', 35, 50, 25, 30, 50)
) AS v(stage, target_min, target_max, stress_threshold, trigger_pct, refill_pct)
WHERE c.name = 'sweet_potato'
  AND iz.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM soil_moisture_target smt
      WHERE smt.zone_id = iz.id AND smt.crop_id = c.id AND smt.growth_stage = v.stage
  );

-- Banana targets
INSERT INTO soil_moisture_target (zone_id, crop_id, growth_stage, target_min_pct, target_max_pct, stress_threshold_pct, irrigation_trigger_pct, refill_to_pct)
SELECT
    iz.id,
    c.id,
    v.stage,
    v.target_min,
    v.target_max,
    v.stress_threshold,
    v.trigger_pct,
    v.refill_pct
FROM irrigation_zone iz
CROSS JOIN crop c
CROSS JOIN (VALUES
    ('planting', 55, 70, 40, 45, 70),
    ('vegetative', 55, 70, 40, 45, 70),
    ('flowering', 60, 75, 45, 50, 75),
    ('fruit_fill', 55, 70, 40, 45, 70),
    ('harvest', 45, 60, 30, 35, 60)
) AS v(stage, target_min, target_max, stress_threshold, trigger_pct, refill_pct)
WHERE c.name = 'banana'
  AND iz.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM soil_moisture_target smt
      WHERE smt.zone_id = iz.id AND smt.crop_id = c.id AND smt.growth_stage = v.stage
  );
