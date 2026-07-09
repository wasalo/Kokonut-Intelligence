-- ============================================================
-- 075_feature_engineering.sql — Time-Series Feature Aggregation
-- Based on ATLAS-SOC simple reducer + time-series summary reducer
-- ============================================================

BEGIN;

-- ============================================================================
-- REMOTE SENSING TIME-SERIES FEATURES
-- ============================================================================

CREATE TABLE IF NOT EXISTS rs_time_series_feature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    target_date DATE NOT NULL,
    -- Reducer type
    reducer_type VARCHAR(50) NOT NULL
        CHECK (reducer_type IN ('simple_median', 'seasonal_median', 'time_series_summary')),
    -- Time window
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    window_months INTEGER,
    -- Season (for seasonal_median)
    season VARCHAR(20)
        CHECK (season IS NULL OR season IN ('spring', 'summer', 'autumn', 'winter')),
    year_offset INTEGER, -- 0 = most recent year, 1 = year before, etc.
    -- Simple reducer features (6-month median)
    ndvi_median NUMERIC(6,4),
    ndre_median NUMERIC(6,4),
    evi_median NUMERIC(6,4),
    savi_median NUMERIC(6,4),
    ndwi_median NUMERIC(6,4),
    satvi_median NUMERIC(6,4),
    bsi_median NUMERIC(6,4),
    nbr2_median NUMERIC(6,4),
    ndti_median NUMERIC(6,4),
    lswi_median NUMERIC(6,4),
    tc_brightness_median NUMERIC(8,4),
    tc_greenness_median NUMERIC(8,4),
    tc_wetness_median NUMERIC(8,4),
    -- Derived
    ndvi_range NUMERIC(6,4),
    ndvi_stddev NUMERIC(6,4),
    -- Source
    source VARCHAR(100),
    observation_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ts_feature_location ON rs_time_series_feature(location_id);
CREATE INDEX IF NOT EXISTS idx_ts_feature_date ON rs_time_series_feature(target_date);
CREATE INDEX IF NOT EXISTS idx_ts_feature_reducer ON rs_time_series_feature(reducer_type);
CREATE INDEX IF NOT EXISTS idx_ts_feature_window ON rs_time_series_feature(window_start, window_end);

COMMENT ON TABLE rs_time_series_feature IS 'Remote sensing time-series features — seasonal medians and time-series summaries for SOC prediction (ATLAS-SOC feature engineering)';

-- ============================================================================
-- WEATHER TIME-SERIES FEATURES
-- ============================================================================

CREATE TABLE IF NOT EXISTS weather_time_series_feature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    target_date DATE NOT NULL,
    -- Reducer type
    reducer_type VARCHAR(50) NOT NULL
        CHECK (reducer_type IN ('seasonal_mean', 'time_series_summary')),
    -- Time window
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    -- Season
    season VARCHAR(20)
        CHECK (season IS NULL OR season IN ('spring', 'summer', 'autumn', 'winter')),
    year_offset INTEGER,
    -- 6-month summaries
    soil_moisture_mean NUMERIC(8,4),
    mean_temp_mean NUMERIC(6,2),
    max_temp_mean NUMERIC(6,2),
    min_temp_mean NUMERIC(6,2),
    precipitation_sum NUMERIC(8,2),
    potential_et_mean NUMERIC(8,2),
    transpiration_mean NUMERIC(8,2),
    solar_radiation_mean NUMERIC(8,2),
    sensible_heat_mean NUMERIC(8,2),
    water_runoff_sum NUMERIC(8,2),
    -- Derived
    temp_range NUMERIC(6,2),
    aridity_index NUMERIC(8,4),
    -- Source
    source VARCHAR(100),
    observation_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weather_ts_location ON weather_time_series_feature(location_id);
CREATE INDEX IF NOT EXISTS idx_weather_ts_date ON weather_time_series_feature(target_date);
CREATE INDEX IF NOT EXISTS idx_weather_ts_reducer ON weather_time_series_feature(reducer_type);

COMMENT ON TABLE weather_time_series_feature IS 'Weather time-series features — seasonal means and multi-year summaries for SOC prediction';

-- ============================================================================
-- MODIS LST TIME-SERIES FEATURES
-- ============================================================================

CREATE TABLE IF NOT EXISTS modis_lst_time_series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    target_date DATE NOT NULL,
    reducer_type VARCHAR(50) NOT NULL
        CHECK (reducer_type IN ('seasonal_mean', 'time_series_summary')),
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    season VARCHAR(20)
        CHECK (season IS NULL OR season IN ('spring', 'summer', 'autumn', 'winter')),
    year_offset INTEGER,
    lst_day_mean NUMERIC(6,2),
    lst_night_mean NUMERIC(6,2),
    lst_diurnal_range NUMERIC(6,2),
    source VARCHAR(100),
    observation_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_modis_ts_location ON modis_lst_time_series(location_id);
CREATE INDEX IF NOT EXISTS idx_modis_ts_date ON modis_lst_time_series(target_date);

COMMENT ON TABLE modis_lst_time_series IS 'MODIS LST time-series features — temperature covariates for SOC prediction';

-- ============================================================================
-- SMAP SOIL MOISTURE TIME-SERIES FEATURES
-- ============================================================================

CREATE TABLE IF NOT EXISTS smap_moisture_time_series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    target_date DATE NOT NULL,
    reducer_type VARCHAR(50) NOT NULL
        CHECK (reducer_type IN ('seasonal_mean', 'time_series_summary')),
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    season VARCHAR(20)
        CHECK (season IS NULL OR season IN ('spring', 'summer', 'autumn', 'winter')),
    year_offset INTEGER,
    soil_moisture_mean NUMERIC(8,4),
    soil_moisture_stddev NUMERIC(8,4),
    source VARCHAR(100),
    observation_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_smap_ts_location ON smap_moisture_time_series(location_id);
CREATE INDEX IF NOT EXISTS idx_smap_ts_date ON smap_moisture_time_series(target_date);

COMMENT ON TABLE smap_moisture_time_series IS 'SMAP soil moisture time-series features — surface hydrology for SOC prediction';

-- ============================================================================
-- SENTINEL-1 SAR TIME-SERIES FEATURES
-- ============================================================================

CREATE TABLE IF NOT EXISTS sentinel1_time_series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    target_date DATE NOT NULL,
    reducer_type VARCHAR(50) NOT NULL
        CHECK (reducer_type IN ('seasonal_median', 'time_series_summary')),
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    season VARCHAR(20)
        CHECK (season IS NULL OR season IN ('spring', 'summer', 'autumn', 'winter')),
    year_offset INTEGER,
    vh_median NUMERIC(8,4),
    vv_median NUMERIC(8,4),
    vh_vv_ratio NUMERIC(6,4),
    source VARCHAR(100),
    observation_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_s1_ts_location ON sentinel1_time_series(location_id);
CREATE INDEX IF NOT EXISTS idx_s1_ts_date ON sentinel1_time_series(target_date);

COMMENT ON TABLE sentinel1_time_series IS 'Sentinel-1 SAR time-series features — all-weather surface observation for SOC prediction';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Complete feature set for a location and target date
CREATE OR REPLACE VIEW v_dsm_feature_set AS
SELECT
    rsl.location_id,
    l.name AS location_name,
    rsl.plot_id,
    rsl.target_date,
    -- Optical remote sensing (simple reducer)
    rsl.ndvi_median,
    rsl.savi_median,
    rsl.satvi_median,
    rsl.bsi_median,
    rsl.nbr2_median,
    rsl.ndti_median,
    rsl.lswi_median,
    rsl.tc_brightness_median,
    rsl.tc_greenness_median,
    rsl.tc_wetness_median,
    rsl.ndvi_range,
    -- Weather (6-month)
    wts.soil_moisture_mean,
    wts.mean_temp_mean,
    wts.precipitation_sum,
    wts.potential_et_mean,
    -- MODIS LST
    mts.lst_day_mean,
    mts.lst_night_mean,
    -- SMAP
    sts.soil_moisture_mean AS smap_moisture_mean,
    -- SAR
    s1s.vh_median,
    s1s.vv_median,
    -- WorldClim
    wc.bio1_mean_annual_temp,
    wc.bio16_precip_wettest_quarter,
    wc.bio17_precip_driest_quarter
FROM rs_time_series_feature rsl
JOIN location l ON rsl.location_id = l.id
LEFT JOIN weather_time_series_feature wts ON wts.location_id = rsl.location_id AND wts.target_date = rsl.target_date AND wts.reducer_type = 'seasonal_mean' AND wts.season IS NULL
LEFT JOIN modis_lst_time_series mts ON mts.location_id = rsl.location_id AND mts.target_date = rsl.target_date AND mts.reducer_type = 'seasonal_mean' AND mts.season IS NULL
LEFT JOIN smap_moisture_time_series sts ON sts.location_id = rsl.location_id AND sts.target_date = rsl.target_date AND sts.reducer_type = 'seasonal_mean' AND sts.season IS NULL
LEFT JOIN sentinel1_time_series s1s ON s1s.location_id = rsl.location_id AND s1s.target_date = rsl.target_date AND s1s.reducer_type = 'seasonal_median' AND s1s.season IS NULL
LEFT JOIN worldclim_climate wc ON wc.location_id = rsl.location_id AND wc.plot_id = rsl.plot_id
WHERE rsl.reducer_type = 'simple_median'
  AND l.status IN ('active', 'verified', 'published');

-- Seasonal feature summary
CREATE OR REPLACE VIEW v_seasonal_feature_summary AS
SELECT
    rsl.location_id,
    l.name AS location_name,
    rsl.season,
    rsl.year_offset,
    AVG(rsl.ndvi_median) AS avg_ndvi,
    AVG(rsl.savi_median) AS avg_savi,
    AVG(rsl.bsi_median) AS avg_bsi,
    AVG(rsl.lswi_median) AS avg_lswi,
    AVG(rsl.tc_greenness_median) AS avg_tc_greenness,
    COUNT(*) AS observation_count
FROM rs_time_series_feature rsl
JOIN location l ON rsl.location_id = l.id
WHERE rsl.reducer_type = 'seasonal_median'
  AND rsl.season IS NOT NULL
  AND l.status IN ('active', 'verified', 'published')
GROUP BY rsl.location_id, l.name, rsl.season, rsl.year_offset;

COMMIT;
