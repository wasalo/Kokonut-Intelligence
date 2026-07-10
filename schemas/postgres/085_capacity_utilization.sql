-- ============================================================
-- 085_capacity_utilization.sql — Capacity Utilization
-- ============================================================

-- 1. Utilization observation (time-series infrastructure usage)
CREATE TABLE IF NOT EXISTS utilization_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    asset_id UUID REFERENCES infrastructure_asset(id) ON DELETE CASCADE,
    observation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    capacity_used NUMERIC(12,4),
    capacity_unit VARCHAR(50),
    total_capacity NUMERIC(12,4),
    utilization_pct NUMERIC(5,2) CHECK (utilization_pct >= 0 AND utilization_pct <= 100),
    usage_hours NUMERIC(8,2),
    production_output NUMERIC(12,4),
    production_unit VARCHAR(50),
    fuel_consumed NUMERIC(8,2),
    energy_consumed_kwh NUMERIC(10,4),
    notes TEXT,
    observed_by UUID REFERENCES staff(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_util_location ON utilization_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_util_asset ON utilization_observation(asset_id);
CREATE INDEX IF NOT EXISTS idx_util_date ON utilization_observation(observation_date);

-- 2. Equipment usage log (individual usage events)
CREATE TABLE IF NOT EXISTS equipment_usage_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    asset_id UUID NOT NULL REFERENCES infrastructure_asset(id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    operation_type VARCHAR(100),
    output_produced NUMERIC(12,4),
    output_unit VARCHAR(50),
    fuel_consumed NUMERIC(8,2),
    energy_consumed_kwh NUMERIC(10,4),
    operator_name VARCHAR(255),
    operator_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eul_location ON equipment_usage_log(location_id);
CREATE INDEX IF NOT EXISTS idx_eul_asset ON equipment_usage_log(asset_id);
CREATE INDEX IF NOT EXISTS idx_eul_time ON equipment_usage_log(start_time, end_time);

-- 3. Capacity threshold (alert configuration)
CREATE TABLE IF NOT EXISTS capacity_threshold (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES infrastructure_asset(id) ON DELETE CASCADE,
    warning_pct NUMERIC(5,2) DEFAULT 80.0 CHECK (warning_pct >= 0 AND warning_pct <= 100),
    critical_pct NUMERIC(5,2) DEFAULT 95.0 CHECK (critical_pct >= 0 AND critical_pct <= 100),
    target_pct NUMERIC(5,2) DEFAULT 70.0 CHECK (target_pct >= 0 AND target_pct <= 100),
    min_pct NUMERIC(5,2) DEFAULT 20.0 CHECK (min_pct >= 0 AND min_pct <= 100),
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_ct_location ON capacity_threshold(location_id);
CREATE INDEX IF NOT EXISTS idx_ct_asset ON capacity_threshold(asset_id);

-- 4. Public view
CREATE OR REPLACE VIEW v_infrastructure_utilization_summary AS
SELECT
    ia.id AS asset_id,
    ia.asset_name,
    ia.asset_type,
    ia.capacity,
    ia.capacity_unit,
    ia.condition_status,
    l.name AS location_name,
    uo_latest.utilization_pct AS latest_utilization,
    uo_latest.observation_date AS latest_observation_date,
    uo_avg.avg_utilization_pct,
    ct.target_pct,
    ct.warning_pct,
    ct.critical_pct,
    CASE
        WHEN uo_latest.utilization_pct IS NULL THEN 'no_data'
        WHEN uo_latest.utilization_pct >= ct.critical_pct THEN 'overcapacity'
        WHEN uo_latest.utilization_pct >= ct.warning_pct THEN 'high'
        WHEN uo_latest.utilization_pct >= ct.min_pct THEN 'optimal'
        WHEN uo_latest.utilization_pct > 0 THEN 'underutilized'
        ELSE 'inactive'
    END AS utilization_status
FROM infrastructure_asset ia
JOIN location l ON l.id = ia.location_id
LEFT JOIN LATERAL (
    SELECT utilization_pct, observation_date
    FROM utilization_observation uo
    WHERE uo.asset_id = ia.id
    ORDER BY uo.observation_date DESC
    LIMIT 1
) uo_latest ON TRUE
LEFT JOIN LATERAL (
    SELECT AVG(utilization_pct) AS avg_utilization_pct
    FROM utilization_observation uo
    WHERE uo.asset_id = ia.id
    AND uo.observation_date >= CURRENT_DATE - INTERVAL '90 days'
) uo_avg ON TRUE
LEFT JOIN capacity_threshold ct ON ct.asset_id = ia.id
WHERE ia.location_id = l.id;
