-- ============================================================
-- 074_dsm_soc_prediction.sql — Digital Soil Mapping & SOC Prediction
-- Based on ATLAS-SOC (Kellner et al. 2025) and Fu et al. (2024)
-- ============================================================

BEGIN;

-- ============================================================================
-- EXTEND REMOTE SENSING WITH SPECTRAL INDICES FOR SOC
-- ============================================================================

-- Additional spectral indices derived from Sentinel-2 bands
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS satvi NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS bsi NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS nbr2 NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS ndti NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS lswi NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS brightness_index NUMERIC(6,4);

-- Tasseled cap transformation coefficients (Sentinel-2)
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS tc_brightness NUMERIC(8,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS tc_greenness NUMERIC(8,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS tc_wetness NUMERIC(8,4);

-- Raw band values needed for index computation
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_blue NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_green NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_red NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_nir NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_swir1 NUMERIC(6,4);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS band_swir2 NUMERIC(6,4);

COMMENT ON COLUMN remote_sensing_observation.satvi IS 'Soil Adjusted Total Vegetation Index (Marsett et al. 2006)';
COMMENT ON COLUMN remote_sensing_observation.bsi IS 'Bare Soil Index — identifies exposed soil pixels';
COMMENT ON COLUMN remote_sensing_observation.nbr2 IS 'Normalized Burn Ratio 2 — moisture/residue indicator';
COMMENT ON COLUMN remote_sensing_observation.ndti IS 'Normalized Difference Tillage Index — tillage status';
COMMENT ON COLUMN remote_sensing_observation.lswi IS 'Land Surface Water Index — soil water content';
COMMENT ON COLUMN remote_sensing_observation.tc_brightness IS 'Tasseled cap brightness (Sentinel-2 coefficients)';
COMMENT ON COLUMN remote_sensing_observation.tc_greenness IS 'Tasseled cap greenness (Sentinel-2 coefficients)';
COMMENT ON COLUMN remote_sensing_observation.tc_wetness IS 'Tasseled cap wetness (Sentinel-2 coefficients)';

-- ============================================================================
-- WORLDCLIM LONG-TERM CLIMATE PROXIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS worldclim_climate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    -- Bioclimatic variables (1970-2000 baseline)
    bio1_mean_annual_temp NUMERIC(6,2),
    bio4_temp_seasonality NUMERIC(8,2),
    bio5_max_temp_warmest_month NUMERIC(6,2),
    bio6_min_temp_coldest_month NUMERIC(6,2),
    bio12_annual_precipitation NUMERIC(8,2),
    bio15_precip_seasonality NUMERIC(6,2),
    bio16_precip_wettest_quarter NUMERIC(8,2),
    bio17_precip_driest_quarter NUMERIC(8,2),
    -- Derived
    temp_range NUMERIC(6,2),
    moisture_index NUMERIC(6,4),
    -- Metadata
    source VARCHAR(100) DEFAULT 'worldclim_v2',
    resolution_m INTEGER DEFAULT 1000,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_worldclim_location ON worldclim_climate(location_id);

COMMENT ON TABLE worldclim_climate IS 'WorldClim v2 bioclimatic variables — long-term climate proxies for SOC prediction (ATLAS-SOC covariate)';

-- ============================================================================
-- NCEP WEATHER SUMMARIES (SHORT-TERM CLIMATE)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ncep_weather_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    target_date DATE NOT NULL,
    -- Source configuration
    source VARCHAR(100) DEFAULT 'ncep_cfs_v1',
    resolution_m INTEGER DEFAULT 30000,
    -- 6-month summaries (arithmetic mean)
    soil_moisture_6m NUMERIC(8,4),
    mean_temp_6m NUMERIC(6,2),
    max_temp_6m NUMERIC(6,2),
    min_temp_6m NUMERIC(6,2),
    precipitation_6m NUMERIC(8,2),
    potential_et_6m NUMERIC(8,2),
    transpiration_6m NUMERIC(8,2),
    solar_radiation_6m NUMERIC(8,2),
    sensible_heat_6m NUMERIC(8,2),
    water_runoff_6m NUMERIC(8,2),
    -- 3-year summaries
    soil_moisture_3y NUMERIC(8,4),
    mean_temp_3y NUMERIC(6,2),
    max_temp_3y NUMERIC(6,2),
    min_temp_3y NUMERIC(6,2),
    precipitation_3y NUMERIC(8,2),
    potential_et_3y NUMERIC(8,2),
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ncep_location ON ncep_weather_summary(location_id);
CREATE INDEX IF NOT EXISTS idx_ncep_date ON ncep_weather_summary(target_date);

COMMENT ON TABLE ncep_weather_summary IS 'NCEP CFS weather summaries — short-term climate covariates for SOC prediction (ATLAS-SOC covariate)';

-- ============================================================================
-- MODIS LAND SURFACE TEMPERATURE
-- ============================================================================

CREATE TABLE IF NOT EXISTS modis_lst_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    target_date DATE NOT NULL,
    -- Source
    source VARCHAR(100) DEFAULT 'modis_mod11a2_v006',
    resolution_m INTEGER DEFAULT 1000,
    -- 6-month mean LST
    lst_day_mean_6m NUMERIC(6,2),
    lst_night_mean_6m NUMERIC(6,2),
    -- Seasonal means (3-month windows)
    lst_day_spring NUMERIC(6,2),
    lst_day_summer NUMERIC(6,2),
    lst_day_autumn NUMERIC(6,2),
    lst_day_winter NUMERIC(6,2),
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_modis_lst_location ON modis_lst_summary(location_id);
CREATE INDEX IF NOT EXISTS idx_modis_lst_date ON modis_lst_summary(target_date);

COMMENT ON TABLE modis_lst_summary IS 'MODIS MOD11A2 land surface temperature summaries — temperature covariate for SOC prediction';

-- ============================================================================
-- SMAP SOIL MOISTURE
-- ============================================================================

CREATE TABLE IF NOT EXISTS smap_soil_moisture (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    target_date DATE NOT NULL,
    -- Source
    source VARCHAR(100) DEFAULT 'smap_l3_daily_9km',
    resolution_m INTEGER DEFAULT 9000,
    -- 6-month mean
    soil_moisture_6m NUMERIC(8,4),
    -- 3-year mean
    soil_moisture_3y NUMERIC(8,4),
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_smap_location ON smap_soil_moisture(location_id);
CREATE INDEX IF NOT EXISTS idx_smap_date ON smap_soil_moisture(target_date);

COMMENT ON TABLE smap_soil_moisture IS 'SMAP L3 soil moisture summaries — surface hydrology covariate for SOC prediction';

-- ============================================================================
-- SENTINEL-1 SAR SUMMARIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS sentinel1_sar_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    target_date DATE NOT NULL,
    -- Source
    source VARCHAR(100) DEFAULT 'sentinel1_grd',
    resolution_m INTEGER DEFAULT 20,
    -- 6-month median
    vh_median_6m NUMERIC(8,4),
    vv_median_6m NUMERIC(8,4),
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_s1_sar_location ON sentinel1_sar_summary(location_id);

COMMENT ON TABLE sentinel1_sar_summary IS 'Sentinel-1 SAR summaries — all-weather surface observation for SOC prediction';

-- ============================================================================
-- SOC PREDICTION MODEL TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS soc_prediction_model (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(200) NOT NULL,
    model_type VARCHAR(100) NOT NULL DEFAULT 'xgboost',
    -- Training configuration
    training_date DATE NOT NULL,
    training_samples INTEGER,
    training_fields INTEGER,
    -- Feature configuration
    feature_count INTEGER,
    feature_names TEXT[],
    -- Performance metrics
    cv_r_squared NUMERIC(6,4),
    cv_rmse NUMERIC(8,4),
    cv_mae NUMERIC(8,4),
    cv_mec NUMERIC(6,4),
    field_level_r_squared NUMERIC(6,4),
    field_level_rmse NUMERIC(8,4),
    -- Depth strategy
    depth_strategy VARCHAR(50) DEFAULT 'full_column'
        CHECK (depth_strategy IN ('surface_only', 'full_column', 'depth_as_feature')),
    depth_range VARCHAR(50) DEFAULT '0-30',
    -- Hyperparameters
    hyperparameters JSONB DEFAULT '{}',
    -- Model artifact reference
    model_artifact_url TEXT,
    model_artifact_hash VARCHAR(255),
    -- Status
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'validated', 'deployed', 'archived')),
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_soc_model_status ON soc_prediction_model(status);

COMMENT ON TABLE soc_prediction_model IS 'SOC prediction model registry — tracks trained models, hyperparameters, and validation metrics';

-- ============================================================================
-- SOC PREDICTION RESULTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS soc_prediction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES soc_prediction_model(id),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    prediction_date DATE NOT NULL,
    -- Prediction
    predicted_soc_pct NUMERIC(6,3),
    predicted_soc_tonnes_ha NUMERIC(10,4),
    prediction_uncertainty NUMERIC(6,4),
    -- Depth
    depth_cm NUMERIC(6,2) DEFAULT 30,
    -- Validation (populated when ground truth available)
    measured_soc_pct NUMERIC(6,3),
    absolute_error NUMERIC(6,4),
    squared_error NUMERIC(8,6),
    percentage_error NUMERIC(6,2),
    -- Spatial
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    point_geometry GEOMETRY(POINT, 4326),
    -- Feature importance at this prediction
    top_features JSONB DEFAULT '[]',
    -- Status
    status VARCHAR(50) DEFAULT 'predicted'
        CHECK (status IN ('predicted', 'validated', 'published', 'superseded')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_soc_pred_model ON soc_prediction(model_id);
CREATE INDEX IF NOT EXISTS idx_soc_pred_location ON soc_prediction(location_id);
CREATE INDEX IF NOT EXISTS idx_soc_pred_date ON soc_prediction(prediction_date);
CREATE INDEX IF NOT EXISTS idx_soc_pred_geometry ON soc_prediction USING GIST(point_geometry);

COMMENT ON TABLE soc_prediction IS 'SOC prediction results — pixel-level and field-level SOC estimates from trained models';

-- ============================================================================
-- FEATURE IMPORTANCE COMPUTATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS computed_feature_importance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES soc_prediction_model(id),
    feature_name VARCHAR(200) NOT NULL,
    importance_score NUMERIC(8,6) NOT NULL,
    importance_type VARCHAR(50) DEFAULT 'gain'
        CHECK (importance_type IN ('gain', 'weight', 'cover', 'total_gain', 'average_gain')),
    feature_class VARCHAR(100),
    feature_type VARCHAR(100),
    rank INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feat_importance_model ON computed_feature_importance(model_id);
CREATE INDEX IF NOT EXISTS idx_feat_importance_rank ON computed_feature_importance(model_id, rank);

COMMENT ON TABLE computed_feature_importance IS 'Computed feature importance from trained SOC prediction models';

-- ============================================================================
-- CROSS-VALIDATION RESULTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS cv_fold_result (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES soc_prediction_model(id),
    fold_number INTEGER NOT NULL,
    cv_strategy VARCHAR(100) NOT NULL DEFAULT 'geographic'
        CHECK (cv_strategy IN ('geographic', 'random', 'leave_one_field', 'spatial_block')),
    -- Fold metrics
    r_squared NUMERIC(6,4),
    rmse NUMERIC(8,4),
    mae NUMERIC(8,4),
    me NUMERIC(8,4),
    mec NUMERIC(6,4),
    intercept NUMERIC(8,4),
    slope NUMERIC(8,4),
    sample_count INTEGER,
    -- Fold info
    excluded_field_ids UUID[],
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cv_fold_model ON cv_fold_result(model_id);

COMMENT ON TABLE cv_fold_result IS 'Cross-validation fold results — per-fold metrics for geographic CV of SOC prediction models';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Public SOC prediction summary
CREATE OR REPLACE VIEW v_public_soc_predictions AS
SELECT
    sp.id,
    sp.model_id,
    spm.model_name,
    sp.location_id,
    l.name AS location_name,
    sp.plot_id,
    p.name AS plot_name,
    sp.prediction_date,
    sp.predicted_soc_pct,
    sp.predicted_soc_tonnes_ha,
    sp.prediction_uncertainty,
    sp.depth_cm,
    sp.measured_soc_pct,
    sp.absolute_error,
    sp.status
FROM soc_prediction sp
JOIN soc_prediction_model spm ON sp.model_id = spm.id
JOIN location l ON sp.location_id = l.id
LEFT JOIN plot p ON sp.plot_id = p.id
WHERE l.status IN ('active', 'verified', 'published')
  AND sp.status IN ('predicted', 'validated', 'published');

-- Model performance summary
CREATE OR REPLACE VIEW v_soc_model_performance AS
SELECT
    spm.id AS model_id,
    spm.model_name,
    spm.model_type,
    spm.training_date,
    spm.training_samples,
    spm.training_fields,
    spm.feature_count,
    spm.cv_r_squared,
    spm.cv_rmse,
    spm.cv_mec,
    spm.field_level_r_squared,
    spm.field_level_rmse,
    spm.depth_strategy,
    spm.status,
    COUNT(DISTINCT sp.id) AS prediction_count,
    COUNT(DISTINCT sp.location_id) AS location_count
FROM soc_prediction_model spm
LEFT JOIN soc_prediction sp ON sp.model_id = spm.id
GROUP BY spm.id, spm.model_name, spm.model_type, spm.training_date,
         spm.training_samples, spm.training_fields, spm.feature_count,
         spm.cv_r_squared, spm.cv_rmse, spm.cv_mec,
         spm.field_level_r_squared, spm.field_level_rmse,
         spm.depth_strategy, spm.status;

-- Feature importance summary per model
CREATE OR REPLACE VIEW v_feature_importance_summary AS
SELECT
    cfi.model_id,
    spm.model_name,
    cfi.feature_class,
    COUNT(*) AS feature_count,
    SUM(cfi.importance_score) AS total_importance,
    AVG(cfi.importance_score) AS avg_importance,
    MAX(cfi.importance_score) AS max_importance,
    MIN(cfi.rank) AS best_rank
FROM computed_feature_importance cfi
JOIN soc_prediction_model spm ON cfi.model_id = spm.id
GROUP BY cfi.model_id, spm.model_name, cfi.feature_class
ORDER BY total_importance DESC;

-- Cross-validation summary
CREATE OR REPLACE VIEW v_cv_summary AS
SELECT
    cvr.model_id,
    spm.model_name,
    cvr.cv_strategy,
    COUNT(*) AS fold_count,
    AVG(cvr.r_squared) AS avg_r_squared,
    AVG(cvr.rmse) AS avg_rmse,
    AVG(cvr.mae) AS avg_mae,
    AVG(cvr.mec) AS avg_mec,
    AVG(cvr.intercept) AS avg_intercept,
    AVG(cvr.slope) AS avg_slope,
    SUM(cvr.sample_count) AS total_samples
FROM cv_fold_result cvr
JOIN soc_prediction_model spm ON cvr.model_id = spm.id
GROUP BY cvr.model_id, spm.model_name, cvr.cv_strategy;

-- Spectral index statistics per location
CREATE OR REPLACE VIEW v_spectral_index_stats AS
SELECT
    rso.location_id,
    l.name AS location_name,
    rso.source,
    COUNT(*) AS observation_count,
    AVG(rso.ndvi) AS avg_ndvi,
    AVG(rso.savi) AS avg_savi,
    AVG(rso.satvi) AS avg_satvi,
    AVG(rso.bsi) AS avg_bsi,
    AVG(rso.nbr2) AS avg_nbr2,
    AVG(rso.ndti) AS avg_ndti,
    AVG(rso.lswi) AS avg_lswi,
    AVG(rso.tc_brightness) AS avg_tc_brightness,
    AVG(rso.tc_greenness) AS avg_tc_greenness,
    AVG(rso.tc_wetness) AS avg_tc_wetness,
    MIN(rso.observation_date) AS first_observation,
    MAX(rso.observation_date) AS last_observation
FROM remote_sensing_observation rso
JOIN location l ON rso.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
GROUP BY rso.location_id, l.name, rso.source;

COMMIT;
