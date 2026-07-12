-- ============================================================
-- 133_geostatistics.sql
-- Geostatistics: variogram modeling, kriging, simulation,
-- spatial autocorrelation, cross-validation, sensor network design
-- ============================================================

BEGIN;

-- ============================================================
-- 1. Add geometry columns to sensor_device and soil_sample
-- ============================================================

ALTER TABLE sensor_device ADD COLUMN IF NOT EXISTS point_geometry GEOMETRY(POINT, 4326);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS point_geometry GEOMETRY(POINT, 4326);

-- Populate from existing lat/lon
UPDATE sensor_device SET point_geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
WHERE point_geometry IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL;

UPDATE soil_sample SET point_geometry = ST_SetSRID(ST_MakePoint(gps_longitude, gps_latitude), 4326)
WHERE point_geometry IS NULL AND gps_latitude IS NOT NULL AND gps_longitude IS NOT NULL;

-- Auto-compute triggers
CREATE OR REPLACE FUNCTION trg_sensor_device_geometry() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
    NEW.point_geometry := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sensor_device_geometry ON sensor_device;
CREATE TRIGGER trg_sensor_device_geometry
  BEFORE INSERT OR UPDATE ON sensor_device
  FOR EACH ROW EXECUTE FUNCTION trg_sensor_device_geometry();

CREATE OR REPLACE FUNCTION trg_soil_sample_geometry() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.gps_latitude IS NOT NULL AND NEW.gps_longitude IS NOT NULL THEN
    NEW.point_geometry := ST_SetSRID(ST_MakePoint(NEW.gps_longitude, NEW.gps_latitude), 4326);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_soil_sample_geometry ON soil_sample;
CREATE TRIGGER trg_soil_sample_geometry
  BEFORE INSERT OR UPDATE ON soil_sample
  FOR EACH ROW EXECUTE FUNCTION trg_soil_sample_geometry();

-- Spatial indexes
CREATE INDEX IF NOT EXISTS idx_sensor_device_point_geometry ON sensor_device USING GIST(point_geometry);
CREATE INDEX IF NOT EXISTS idx_soil_sample_point_geometry ON soil_sample USING GIST(point_geometry);

-- ============================================================
-- 2. Variogram Model — fitted variogram parameters per location/property
-- ============================================================

CREATE TABLE IF NOT EXISTS variogram_model (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    property_key VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL
        CHECK (model_type IN ('spherical', 'exponential', 'gaussian', 'matern')),
    sill DOUBLE PRECISION NOT NULL,
    range DOUBLE PRECISION NOT NULL,
    nugget DOUBLE PRECISION NOT NULL DEFAULT 0,
    partial_sill DOUBLE PRECISION,
    lag_distance DOUBLE PRECISION,
    lag_tolerance DOUBLE PRECISION,
    bandwidth DOUBLE PRECISION,
    n_pairs INTEGER,
    r_squared DOUBLE PRECISION,
    fitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE variogram_model IS 'Fitted variogram model parameters per location and property';
COMMENT ON COLUMN variogram_model.property_key IS 'Measured property, e.g. soil_carbon, soil_moisture, ndvi';
COMMENT ON COLUMN variogram_model.model_type IS 'Parametric variogram model type';
COMMENT ON COLUMN variogram_model.sill IS 'Total variance at the sill (plateau)';
COMMENT ON COLUMN variogram_model.range IS 'Lag distance at which the variogram reaches the sill, in meters';
COMMENT ON COLUMN variogram_model.nugget IS 'Nugget effect: measurement error + micro-scale variability';
COMMENT ON COLUMN variogram_model.partial_sill IS 'Partial sill = sill - nugget';

CREATE INDEX IF NOT EXISTS idx_variogram_model_location ON variogram_model(location_id);
CREATE INDEX IF NOT EXISTS idx_variogram_model_property ON variogram_model(property_key);

-- ============================================================
-- 3. Kriging Prediction — interpolated surfaces with uncertainty
-- ============================================================

CREATE TABLE IF NOT EXISTS kriging_prediction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    variogram_model_id UUID NOT NULL REFERENCES variogram_model(id),
    property_key VARCHAR(100) NOT NULL,
    grid_resolution_m DOUBLE PRECISION,
    n_points INTEGER NOT NULL,
    method VARCHAR(50) NOT NULL
        CHECK (method IN ('ordinary', 'simple', 'indicator')),
    threshold_value DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE kriging_prediction IS 'Kriging interpolation run metadata';

CREATE TABLE IF NOT EXISTS kriging_point (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES kriging_prediction(id) ON DELETE CASCADE,
    point_geometry GEOMETRY(POINT, 4326) NOT NULL,
    predicted_value DOUBLE PRECISION NOT NULL,
    prediction_variance DOUBLE PRECISION,
    prediction_std DOUBLE PRECISION,
    search_radius_m DOUBLE PRECISION,
    n_neighbors INTEGER,
    weight_sum DOUBLE PRECISION
);

COMMENT ON TABLE kriging_point IS 'Per-point kriging predictions with uncertainty estimates';

CREATE INDEX IF NOT EXISTS idx_kriging_point_geometry ON kriging_point USING GIST(point_geometry);
CREATE INDEX IF NOT EXISTS idx_kriging_point_prediction_id ON kriging_point(prediction_id);

-- ============================================================
-- 4. Geostat Realization — multiple simulation realizations for uncertainty
-- ============================================================

CREATE TABLE IF NOT EXISTS geostat_realization (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    variogram_model_id UUID NOT NULL REFERENCES variogram_model(id),
    property_key VARCHAR(100) NOT NULL,
    realization_number INTEGER NOT NULL,
    grid_resolution_m DOUBLE PRECISION,
    n_points INTEGER NOT NULL,
    method VARCHAR(50) NOT NULL
        CHECK (method IN ('sgs', 'sis', 'turning_bands')),
    seed INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE geostat_realization IS 'Sequential Gaussian Simulation realizations for uncertainty quantification';

CREATE TABLE IF NOT EXISTS geostat_realization_point (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    realization_id UUID NOT NULL REFERENCES geostat_realization(id) ON DELETE CASCADE,
    point_geometry GEOMETRY(POINT, 4326) NOT NULL,
    simulated_value DOUBLE PRECISION NOT NULL
);

COMMENT ON TABLE geostat_realization_point IS 'Per-point simulated values for a single realization';

CREATE INDEX IF NOT EXISTS idx_geostat_realization_point_geometry
    ON geostat_realization_point USING GIST(point_geometry);
CREATE INDEX IF NOT EXISTS idx_geostat_realization_point_realization_id
    ON geostat_realization_point(realization_id);

-- ============================================================
-- 5. Spatial Autocorrelation — Moran's I, Geary's C results
-- ============================================================

CREATE TABLE IF NOT EXISTS spatial_autocorrelation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    property_key VARCHAR(100) NOT NULL,
    metric VARCHAR(50) NOT NULL
        CHECK (metric IN ('morans_i', 'gearys_c', 'join_count')),
    statistic_value DOUBLE PRECISION NOT NULL,
    expected_value DOUBLE PRECISION,
    p_value DOUBLE PRECISION,
    z_score DOUBLE PRECISION,
    n_samples INTEGER NOT NULL,
    spatial_weights_type VARCHAR(50)
        CHECK (spatial_weights_type IN ('queen', 'rook', 'distance', 'knn')),
    distance_threshold DOUBLE PRECISION,
    k_neighbors INTEGER,
    interpretation TEXT,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE spatial_autocorrelation IS 'Spatial autocorrelation statistics (Moran I, Geary C)';
COMMENT ON COLUMN spatial_autocorrelation.interpretation IS 'clustered, dispersed, or random';

CREATE INDEX IF NOT EXISTS idx_spatial_autocorrelation_location ON spatial_autocorrelation(location_id);

-- ============================================================
-- 6. Geostat CV Result — spatial cross-validation metrics
-- ============================================================

CREATE TABLE IF NOT EXISTS geostat_cv_result (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    property_key VARCHAR(100) NOT NULL,
    variogram_model_id UUID REFERENCES variogram_model(id),
    cv_strategy VARCHAR(50) NOT NULL
        CHECK (cv_strategy IN ('spatial_block', 'leave_one_out', 'k_fold')),
    n_folds INTEGER NOT NULL,
    block_size_m DOUBLE PRECISION,
    mean_error DOUBLE PRECISION,
    mean_squared_error DOUBLE PRECISION,
    root_mean_squared_error DOUBLE PRECISION,
    mean_absolute_error DOUBLE PRECISION,
    r_squared DOUBLE PRECISION,
    fold_results JSONB DEFAULT '[]',
    soc_model_id UUID,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE geostat_cv_result IS 'Spatial cross-validation results for geostatistical models';

CREATE INDEX IF NOT EXISTS idx_geostat_cv_result_location ON geostat_cv_result(location_id);

-- ============================================================
-- 7. Sensor Network Design — optimal spacing recommendations
-- ============================================================

CREATE TABLE IF NOT EXISTS sensor_network_design (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    property_key VARCHAR(100) NOT NULL,
    variogram_model_id UUID REFERENCES variogram_model(id),
    optimal_spacing_m DOUBLE PRECISION,
    coverage_radius_m DOUBLE PRECISION,
    recommended_n_sensors INTEGER,
    current_n_sensors INTEGER,
    coverage_gap_pct DOUBLE PRECISION,
    confidence_level DOUBLE PRECISION,
    notes TEXT,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sensor_network_design IS 'Optimal sensor network design derived from variogram range';

-- ============================================================
-- 8. Public views
-- ============================================================

CREATE OR REPLACE VIEW v_public_variogram_models AS
SELECT
    vm.id,
    vm.location_id,
    vm.property_key,
    vm.model_type,
    vm.sill,
    vm.range,
    vm.nugget,
    vm.partial_sill,
    vm.r_squared,
    vm.fitted_at,
    vm.created_at
FROM variogram_model vm
WHERE vm.location_id IN (
    SELECT id FROM location WHERE status IN ('verified', 'published')
);

CREATE OR REPLACE VIEW v_public_kriging_summary AS
SELECT
    kp.id AS prediction_id,
    kp.location_id,
    kp.property_key,
    kp.method,
    kp.grid_resolution_m,
    kp.n_points,
    kp.created_at,
    AVG(kpt.predicted_value) AS mean_predicted,
    AVG(kpt.prediction_variance) AS mean_variance,
    AVG(kpt.prediction_std) AS mean_std,
    MIN(kpt.predicted_value) AS min_predicted,
    MAX(kpt.predicted_value) AS max_predicted
FROM kriging_prediction kp
JOIN kriging_point kpt ON kpt.prediction_id = kp.id
GROUP BY kp.id, kp.location_id, kp.property_key, kp.method,
         kp.grid_resolution_m, kp.n_points, kp.created_at;

CREATE OR REPLACE VIEW v_public_autocorrelation_summary AS
SELECT
    sa.id,
    sa.location_id,
    sa.property_key,
    sa.metric,
    sa.statistic_value,
    sa.p_value,
    sa.z_score,
    sa.interpretation,
    sa.n_samples,
    sa.computed_at
FROM spatial_autocorrelation sa
WHERE sa.location_id IN (
    SELECT id FROM location WHERE status IN ('verified', 'published')
);

CREATE OR REPLACE VIEW v_public_geostat_summary AS
SELECT
    vm.location_id,
    vm.property_key,
    vm.model_type,
    vm.sill,
    vm.range,
    vm.nugget,
    sa.statistic_value AS morans_i,
    sa.interpretation AS spatial_pattern,
    snd.optimal_spacing_m,
    snd.recommended_n_sensors,
    snd.current_n_sensors,
    snd.coverage_gap_pct
FROM variogram_model vm
LEFT JOIN spatial_autocorrelation sa
    ON sa.location_id = vm.location_id
    AND sa.property_key = vm.property_key
    AND sa.metric = 'morans_i'
LEFT JOIN sensor_network_design snd
    ON snd.location_id = vm.location_id
    AND snd.property_key = vm.property_key;

COMMIT;
