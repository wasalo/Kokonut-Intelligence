-- 152_energy_monitoring.sql
-- Energy Monitoring: sources, consumption/production readings,
-- efficiency metrics, and renewable energy tracking.

BEGIN;

-- ============================================================
-- ENERGY SOURCES
-- ============================================================

CREATE TABLE IF NOT EXISTS energy_source (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    source_name     VARCHAR(200) NOT NULL,
    source_type     VARCHAR(100) NOT NULL
        CHECK (source_type IN (
            'grid', 'diesel_generator', 'solar', 'wind',
            'biogas', 'biomass', 'battery'
        )),
    capacity_kw     NUMERIC(10,2),
    installation_date DATE,
    status          VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'maintenance', 'decommissioned')),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_energy_source_location
    ON energy_source (location_id, status);
CREATE INDEX IF NOT EXISTS idx_energy_source_type
    ON energy_source (source_type, status);

-- ============================================================
-- ENERGY READINGS
-- ============================================================

CREATE TABLE IF NOT EXISTS energy_reading (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    source_id       UUID NOT NULL REFERENCES energy_source(id) ON DELETE CASCADE,
    reading_date    DATE NOT NULL,
    reading_type    VARCHAR(50) NOT NULL
        CHECK (reading_type IN ('consumption', 'production')),
    kwh             NUMERIC(10,2) NOT NULL,
    cost_per_kwh    NUMERIC(8,4),
    total_cost      NUMERIC(10,2),
    activity_type   VARCHAR(100)
        CHECK (activity_type IN (
            'irrigation', 'processing', 'storage', 'lighting',
            'pump', 'other'
        )),
    equipment_id    UUID,
    notes           TEXT,
    status          VARCHAR(50) DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'verified', 'approved', 'rejected')),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_energy_reading_location
    ON energy_reading (location_id, reading_date DESC);
CREATE INDEX IF NOT EXISTS idx_energy_reading_source
    ON energy_reading (source_id, reading_date DESC);
CREATE INDEX IF NOT EXISTS idx_energy_reading_date
    ON energy_reading (reading_date DESC);
CREATE INDEX IF NOT EXISTS idx_energy_reading_activity
    ON energy_reading (activity_type, reading_date DESC)
    WHERE activity_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_energy_reading_status
    ON energy_reading (status, reading_date DESC);

-- ============================================================
-- ENERGY EFFICIENCY LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS energy_efficiency_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    log_date        DATE NOT NULL,
    period          VARCHAR(50) NOT NULL DEFAULT 'daily'
        CHECK (period IN ('daily', 'weekly', 'monthly')),
    total_consumption_kwh NUMERIC(10,2),
    total_production_kwh  NUMERIC(10,2),
    net_energy_kwh        NUMERIC(10,2),
    renewable_pct         NUMERIC(5,2),
    carbon_intensity_kg_kwh NUMERIC(8,4),
    cost_per_unit_output  NUMERIC(10,4),
    notes           TEXT,
    status          VARCHAR(50) DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'verified', 'approved', 'rejected')),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_energy_efficiency_location
    ON energy_efficiency_log (location_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_energy_efficiency_period
    ON energy_efficiency_log (period, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_energy_efficiency_status
    ON energy_efficiency_log (status, log_date DESC);

-- ============================================================
-- RENEWABLE ENERGY SOURCE
-- ============================================================

CREATE TABLE IF NOT EXISTS renewable_energy_source (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    source_id           UUID NOT NULL REFERENCES energy_source(id) ON DELETE CASCADE,
    renewable_type      VARCHAR(100) NOT NULL
        CHECK (renewable_type IN (
            'solar_pv', 'solar_thermal', 'wind', 'biogas', 'micro_hydro'
        )),
    rated_capacity_kw   NUMERIC(10,2),
    annual_generation_kwh NUMERIC(12,2),
    carbon_offset_kg    NUMERIC(10,2),
    status              VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'maintenance', 'decommissioned')),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_renewable_energy_location
    ON renewable_energy_source (location_id, status);
CREATE INDEX IF NOT EXISTS idx_renewable_energy_type
    ON renewable_energy_source (renewable_type, status);
CREATE INDEX IF NOT EXISTS idx_renewable_energy_source
    ON renewable_energy_source (source_id);

-- ============================================================
-- VIEWS
-- ============================================================

-- Consumption by activity and source
CREATE OR REPLACE VIEW v_energy_consumption AS
SELECT
    er.location_id,
    l.name AS location_name,
    es.source_name,
    es.source_type,
    er.activity_type,
    er.reading_date,
    er.reading_type,
    er.kwh,
    er.cost_per_kwh,
    er.total_cost,
    er.status
FROM energy_reading er
JOIN location l ON l.id = er.location_id
JOIN energy_source es ON es.id = er.source_id
WHERE er.reading_type = 'consumption';

-- Efficiency metrics over time
CREATE OR REPLACE VIEW v_energy_efficiency_trends AS
SELECT
    eel.location_id,
    l.name AS location_name,
    eel.log_date,
    eel.period,
    eel.total_consumption_kwh,
    eel.total_production_kwh,
    eel.net_energy_kwh,
    eel.renewable_pct,
    eel.carbon_intensity_kg_kwh,
    eel.cost_per_unit_output,
    eel.status
FROM energy_efficiency_log eel
JOIN location l ON l.id = eel.location_id;

-- Renewable energy share and carbon offset
CREATE OR REPLACE VIEW v_renewable_summary AS
SELECT
    res.location_id,
    l.name AS location_name,
    res.renewable_type,
    es.source_name,
    res.rated_capacity_kw,
    res.annual_generation_kwh,
    res.carbon_offset_kg,
    res.status
FROM renewable_energy_source res
JOIN location l ON l.id = res.location_id
JOIN energy_source es ON es.id = res.source_id;

-- ============================================================
-- SEED: Common energy cost factors for East Africa
-- ============================================================

-- Seed energy sources for the Adelphi pilot farm
INSERT INTO energy_source (id, location_id, source_name, source_type, capacity_kw, installation_date, status)
SELECT
    gen_random_uuid(),
    l.id,
    v.source_name,
    v.source_type,
    v.capacity_kw,
    v.installation_date,
    'active'
FROM location l
CROSS JOIN (VALUES
    ('KPLC Grid Connection', 'grid', 50.00, DATE '2024-01-15'),
    ('Backup Diesel Generator', 'diesel_generator', 30.00, DATE '2024-01-15'),
    ('Rooftop Solar PV', 'solar', 15.00, DATE '2024-06-01')
) AS v(source_name, source_type, capacity_kw, installation_date)
WHERE l.slug = 'adelphi'
  AND NOT EXISTS (
      SELECT 1 FROM energy_source es
      WHERE es.location_id = l.id AND es.source_name = v.source_name
  );

-- Seed renewable energy details for the solar installation
INSERT INTO renewable_energy_source (
    id, location_id, source_id, renewable_type,
    rated_capacity_kw, annual_generation_kwh, carbon_offset_kg, status
)
SELECT
    gen_random_uuid(),
    es.location_id,
    es.id,
    'solar_pv',
    es.capacity_kw,
    ROUND((es.capacity_kw * 1500)::numeric, 2),
    ROUND((es.capacity_kw * 1500 * 0.4)::numeric, 2),
    'active'
FROM energy_source es
JOIN location l ON l.id = es.location_id
WHERE l.slug = 'adelphi'
  AND es.source_type = 'solar'
  AND NOT EXISTS (
      SELECT 1 FROM renewable_energy_source res
      WHERE res.source_id = es.id
  );

COMMIT;
