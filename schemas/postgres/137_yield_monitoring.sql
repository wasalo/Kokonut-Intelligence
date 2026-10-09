-- ============================================================
-- Yield Monitoring
-- Harvest yield data collection, yield mapping, yield prediction.
-- ============================================================

-- Harvest yield observation (per plot or zone)
CREATE TABLE IF NOT EXISTS harvest_yield_observation (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id         UUID REFERENCES plot(id),
    crop_cycle_id   UUID REFERENCES crop_cycle(id),
    harvest_date    DATE NOT NULL,
    crop_name       VARCHAR(200),
    variety         VARCHAR(200),

    -- Yield measurement
    yield_amount    NUMERIC(12,4) NOT NULL,
    yield_unit      VARCHAR(50) NOT NULL DEFAULT 'kg/ha',
    area_ha         NUMERIC(8,4) NOT NULL DEFAULT 1.0,
    total_yield     NUMERIC(14,4),

    -- Quality metrics
    moisture_content_pct    NUMERIC(5,2),
    grade                  VARCHAR(50),
    foreign_material_pct    NUMERIC(5,2),

    -- Source tracking
    source_type     VARCHAR(50) NOT NULL DEFAULT 'manual',
    source_system   VARCHAR(200),
    source_id       VARCHAR(200),
    metadata        JSONB DEFAULT '{}',

    -- Lifecycle
    status          VARCHAR(50) NOT NULL DEFAULT 'draft',
    verified        BOOLEAN DEFAULT FALSE,
    verified_by     VARCHAR(200),
    verified_at     TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(200),
    updated_by      VARCHAR(200),

    CONSTRAINT uq_yield_observation_source UNIQUE (location_id, source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_yield_observation_location ON harvest_yield_observation (location_id);
CREATE INDEX IF NOT EXISTS idx_yield_observation_plot ON harvest_yield_observation (plot_id);
CREATE INDEX IF NOT EXISTS idx_yield_observation_crop ON harvest_yield_observation (crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_yield_observation_date ON harvest_yield_observation (harvest_date);
CREATE INDEX IF NOT EXISTS idx_yield_observation_status ON harvest_yield_observation (status);

-- Yield prediction
CREATE TABLE IF NOT EXISTS yield_prediction (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    crop_cycle_id   UUID REFERENCES crop_cycle(id),
    plot_id         UUID REFERENCES plot(id),
    prediction_date DATE NOT NULL,

    -- Prediction
    predicted_yield     NUMERIC(12,4) NOT NULL,
    yield_unit          VARCHAR(50) NOT NULL DEFAULT 'kg/ha',
    confidence_interval_low   NUMERIC(12,4),
    confidence_interval_high  NUMERIC(12,4),
    confidence_level    NUMERIC(3,2) DEFAULT 0.95,

    -- Model info
    model_name          VARCHAR(200) DEFAULT 'ensemble',
    model_version       VARCHAR(50),
    features_used       JSONB DEFAULT '[]',
    feature_importance  JSONB DEFAULT '{}',

    -- Inputs used
    days_to_harvest     INTEGER,
    current_gdd         NUMERIC(8,2),
    accumulated_rainfall_mm NUMERIC(8,2),
    avg_temperature_c   NUMERIC(5,2),
    soil_nitrogen_ppm   NUMERIC(6,2),

    -- Evaluation
    actual_yield        NUMERIC(12,4),
    prediction_error    NUMERIC(8,4),
    error_pct           NUMERIC(6,2),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_yield_prediction_location ON yield_prediction (location_id);
CREATE INDEX IF NOT EXISTS idx_yield_prediction_crop ON yield_prediction (crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_yield_prediction_date ON yield_prediction (prediction_date);

-- Yield benchmark (historical averages, targets)
CREATE TABLE IF NOT EXISTS yield_benchmark (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    crop_name       VARCHAR(200) NOT NULL,
    variety         VARCHAR(200),
    benchmark_type  VARCHAR(50) NOT NULL DEFAULT 'historical_avg',
    benchmark_year  INTEGER,
    yield_value     NUMERIC(12,4) NOT NULL,
    yield_unit      VARCHAR(50) NOT NULL DEFAULT 'kg/ha',
    source          VARCHAR(200),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_yield_benchmark_location ON yield_benchmark (location_id);
CREATE INDEX IF NOT EXISTS idx_yield_benchmark_crop ON yield_benchmark (crop_name);

-- ============================================================
-- Public Views
-- ============================================================

CREATE OR REPLACE VIEW v_public_yield_summary AS
SELECT
    hyo.location_id,
    hyo.crop_name,
    hyo.harvest_date,
    EXTRACT(YEAR FROM hyo.harvest_date) AS harvest_year,
    AVG(hyo.yield_amount) AS avg_yield_per_ha,
    SUM(hyo.total_yield) AS total_yield,
    COUNT(*) AS observation_count,
    AVG(hyo.moisture_content_pct) AS avg_moisture_pct
FROM harvest_yield_observation hyo
JOIN farm_registry_record frr ON frr.id = hyo.location_id
WHERE hyo.status IN ('verified', 'published')
  AND frr.status IN ('verified', 'published')
GROUP BY hyo.location_id, hyo.crop_name, hyo.harvest_date
ORDER BY hyo.harvest_date DESC;

CREATE OR REPLACE VIEW v_yield_trend AS
SELECT
    location_id,
    crop_name,
    EXTRACT(YEAR FROM harvest_date) AS year,
    AVG(yield_amount) AS avg_yield,
    MIN(yield_amount) AS min_yield,
    MAX(yield_amount) AS max_yield,
    COUNT(*) AS observations
FROM harvest_yield_observation
WHERE status IN ('verified', 'published')
GROUP BY location_id, crop_name, EXTRACT(YEAR FROM harvest_date)
ORDER BY location_id, crop_name, year;

CREATE OR REPLACE VIEW v_yield_prediction_accuracy AS
SELECT
    yp.location_id,
    yp.crop_cycle_id,
    yp.model_name,
    yp.prediction_date,
    yp.predicted_yield,
    yp.actual_yield,
    yp.prediction_error,
    yp.error_pct,
    ABS(yp.error_pct) AS abs_error_pct
FROM yield_prediction yp
WHERE yp.actual_yield IS NOT NULL
ORDER BY yp.prediction_date DESC;
