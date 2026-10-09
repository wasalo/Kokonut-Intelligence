-- ============================================================
-- 087_geostat_defaults.sql
-- Default variogram configurations for common farm properties
-- ============================================================

BEGIN;

-- Default variogram model configurations
CREATE TABLE IF NOT EXISTS geostat_default_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_key VARCHAR(100) NOT NULL UNIQUE,
    model_type VARCHAR(50) NOT NULL
        CHECK (model_type IN ('spherical', 'exponential', 'gaussian', 'matern')),
    lag_distance DOUBLE PRECISION NOT NULL,
    lag_tolerance DOUBLE PRECISION NOT NULL,
    default_range_m DOUBLE PRECISION NOT NULL,
    default_nugget DOUBLE PRECISION DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE geostat_default_config IS 'Default variogram configurations per property key';

INSERT INTO geostat_default_config (property_key, model_type, lag_distance, lag_tolerance, default_range_m, default_nugget, description)
VALUES
    ('soil_carbon', 'exponential', 50.0, 25.0, 500.0, 0.05, 'Soil organic carbon — moderate spatial continuity'),
    ('soil_moisture', 'spherical', 25.0, 12.5, 300.0, 0.02, 'Soil moisture — short-range spatial structure'),
    ('soil_ph', 'gaussian', 100.0, 50.0, 800.0, 0.01, 'Soil pH — smooth spatial variation'),
    ('ndvi', 'exponential', 200.0, 100.0, 2000.0, 0.1, 'Vegetation index — landscape-scale patterns'),
    ('rainfall', 'spherical', 1000.0, 500.0, 10000.0, 0.0, 'Precipitation — regional spatial structure'),
    ('temperature', 'gaussian', 500.0, 250.0, 5000.0, 0.0, 'Air temperature — smooth spatial gradient')
ON CONFLICT (property_key) DO UPDATE
SET model_type = EXCLUDED.model_type,
    lag_distance = EXCLUDED.lag_distance,
    lag_tolerance = EXCLUDED.lag_tolerance,
    default_range_m = EXCLUDED.default_range_m,
    default_nugget = EXCLUDED.default_nugget,
    description = EXCLUDED.description;

-- View for public access
CREATE OR REPLACE VIEW v_public_geostat_defaults AS
SELECT
    property_key,
    model_type,
    lag_distance,
    lag_tolerance,
    default_range_m,
    default_nugget,
    description
FROM geostat_default_config
ORDER BY property_key;

COMMIT;
