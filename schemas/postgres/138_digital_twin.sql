-- ============================================================
-- Digital Twin
-- Simulated farm environment for what-if analysis and forecasting.
-- ============================================================

-- Digital twin definition
CREATE TABLE IF NOT EXISTS digital_twin (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    name            VARCHAR(300) NOT NULL,
    description     TEXT,
    twin_type       VARCHAR(100) NOT NULL DEFAULT 'crop_simulation',
    status          VARCHAR(50) NOT NULL DEFAULT 'draft',

    -- Simulation parameters
    time_horizon_days   INTEGER NOT NULL DEFAULT 365,
    time_step_hours     INTEGER NOT NULL DEFAULT 24,
    start_date          DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date            DATE,

    -- State
    last_run_at     TIMESTAMPTZ,
    run_count       INTEGER DEFAULT 0,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(200),
    updated_by      VARCHAR(200)
);

CREATE INDEX IF NOT EXISTS idx_digital_twin_location ON digital_twin (location_id);
CREATE INDEX IF NOT EXISTS idx_digital_twin_type ON digital_twin (twin_type);

-- Simulation configuration (parameters for the model)
CREATE TABLE IF NOT EXISTS simulation_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id         UUID NOT NULL REFERENCES digital_twin(id) ON DELETE CASCADE,
    config_key      VARCHAR(200) NOT NULL,
    config_value    JSONB NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_simulation_config UNIQUE (twin_id, config_key)
);

-- Simulation run (execution record)
CREATE TABLE IF NOT EXISTS simulation_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id         UUID NOT NULL REFERENCES digital_twin(id) ON DELETE CASCADE,
    run_label       VARCHAR(300),
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',

    -- Timing
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,

    -- Parameters override for this run
    parameters      JSONB DEFAULT '{}',

    -- Results summary
    final_yield         NUMERIC(12,4),
    final_yield_unit    VARCHAR(50) DEFAULT 'kg/ha',
    total_water_mm      NUMERIC(10,2),
    total_nitrogen_kg   NUMERIC(10,2),
    avg_soil_carbon_pct NUMERIC(6,3),
    total_cost_usd      NUMERIC(12,2),
    total_revenue_usd   NUMERIC(12,2),
    net_margin_usd      NUMERIC(12,2),

    -- Error tracking
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_simulation_run_twin ON simulation_run (twin_id);
CREATE INDEX IF NOT EXISTS idx_simulation_run_status ON simulation_run (status);

-- Simulation state snapshots (daily or per timestep)
CREATE TABLE IF NOT EXISTS simulation_state (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES simulation_run(id) ON DELETE CASCADE,
    day_number      INTEGER NOT NULL,
    state_date      DATE NOT NULL,

    -- Soil state
    soil_moisture_pct   NUMERIC(5,2),
    soil_nitrogen_ppm   NUMERIC(6,2),
    soil_carbon_pct     NUMERIC(6,3),
    soil_temperature_c  NUMERIC(5,2),

    -- Crop state
    gdd_accumulated     NUMERIC(8,2),
    crop_biomass_kg_ha  NUMERIC(10,2),
    leaf_area_index     NUMERIC(6,3),
    crop_stage          VARCHAR(100),
    root_depth_cm       NUMERIC(6,2),

    -- Water
    rainfall_mm         NUMERIC(8,2),
    irrigation_mm       NUMERIC(8,2),
    et_actual_mm        NUMERIC(8,2),
    drainage_mm         NUMERIC(8,2),

    -- Weather inputs
    temp_avg_c          NUMERIC(5,2),
    temp_min_c          NUMERIC(5,2),
    temp_max_c          NUMERIC(5,2),
    solar_radiation_mj  NUMERIC(6,2),
    humidity_pct        NUMERIC(5,2),
    wind_speed_kmh      NUMERIC(5,2),

    -- Carbon
    carbon_sequestered_kg_ha NUMERIC(10,4),
    carbon_emitted_kg_ha     NUMERIC(10,4),

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_simulation_state_run ON simulation_state (run_id);
CREATE INDEX IF NOT EXISTS idx_simulation_state_day ON simulation_state (run_id, day_number);

-- What-if scenario (parameter variations)
CREATE TABLE IF NOT EXISTS what_if_scenario (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id         UUID NOT NULL REFERENCES digital_twin(id) ON DELETE CASCADE,
    name            VARCHAR(300) NOT NULL,
    description     TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'draft',

    -- Scenario parameters (overrides applied to base simulation)
    parameters      JSONB NOT NULL DEFAULT '{}',
    category        VARCHAR(100) DEFAULT 'management',

    -- Results (populated after run)
    run_id          UUID REFERENCES simulation_run(id),
    comparison_summary JSONB DEFAULT '{}',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_what_if_scenario_twin ON what_if_scenario (twin_id);

-- ============================================================
-- Public Views
-- ============================================================

CREATE OR REPLACE VIEW v_public_digital_twins AS
SELECT
    dt.id,
    dt.location_id,
    dt.name,
    dt.twin_type,
    dt.status,
    dt.time_horizon_days,
    dt.start_date,
    dt.last_run_at,
    dt.run_count,
    (SELECT COUNT(*) FROM what_if_scenario ws WHERE ws.twin_id = dt.id) AS scenario_count,
    dt.created_at
FROM digital_twin dt
WHERE dt.status IN ('active', 'archived')
ORDER BY dt.created_at DESC;

CREATE OR REPLACE VIEW v_simulation_run_summary AS
SELECT
    sr.id AS run_id,
    sr.twin_id,
    dt.name AS twin_name,
    dt.location_id,
    sr.status,
    sr.run_label,
    sr.started_at,
    sr.completed_at,
    sr.duration_ms,
    sr.final_yield,
    sr.total_water_mm,
    sr.total_nitrogen_kg,
    sr.total_cost_usd,
    sr.total_revenue_usd,
    sr.net_margin_usd,
    sr.parameters
FROM simulation_run sr
JOIN digital_twin dt ON dt.id = sr.twin_id
ORDER BY sr.created_at DESC;

CREATE OR REPLACE VIEW v_what_if_comparison AS
SELECT
    ws.id AS scenario_id,
    ws.twin_id,
    ws.name AS scenario_name,
    ws.category,
    sr.status AS run_status,
    sr.final_yield,
    sr.total_cost_usd,
    sr.total_revenue_usd,
    sr.net_margin_usd,
    sr.duration_ms,
    ws.comparison_summary,
    ws.created_at
FROM what_if_scenario ws
LEFT JOIN simulation_run sr ON sr.id = ws.run_id
ORDER BY ws.created_at DESC;
