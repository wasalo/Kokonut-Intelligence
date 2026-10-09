-- 134_weather_forecast.sql
-- Weather forecast storage, crop growth stage tracking, and GDD configuration
-- Precision Agriculture Phase 1: Forecast + ET + Phenology

BEGIN;

-- ============================================================
-- WEATHER FORECAST
-- ============================================================

CREATE TABLE IF NOT EXISTS weather_forecast (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    source VARCHAR(100) NOT NULL DEFAULT 'openweathermap',
    forecast_date DATE NOT NULL,
    forecast_hour INTEGER NOT NULL CHECK (forecast_hour IN (0, 3, 6, 9, 12, 15, 18, 21)),
    temp_c NUMERIC(5,2),
    temp_min_c NUMERIC(5,2),
    temp_max_c NUMERIC(5,2),
    feels_like_c NUMERIC(5,2),
    humidity_pct NUMERIC(5,2),
    precipitation_mm NUMERIC(8,2),
    precipitation_prob_pct NUMERIC(5,2),
    rain_3h_mm NUMERIC(8,2),
    wind_speed_kmh NUMERIC(6,2),
    wind_direction_deg NUMERIC(5,2),
    wind_gust_kmh NUMERIC(6,2),
    cloud_cover_pct NUMERIC(5,2),
    visibility_km NUMERIC(6,2),
    pressure_hpa NUMERIC(8,2),
    uv_index NUMERIC(5,2),
    solar_radiation_wm2 NUMERIC(8,2),
    description VARCHAR(255),
    et0_estimate_mm NUMERIC(8,4),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, forecast_date, forecast_hour, source)
);

CREATE INDEX IF NOT EXISTS idx_weather_forecast_lookup
    ON weather_forecast(location_id, forecast_date, forecast_hour);

CREATE INDEX IF NOT EXISTS idx_weather_forecast_location_date
    ON weather_forecast(location_id, forecast_date);

-- Daily forecast summary view
CREATE OR REPLACE VIEW v_weather_forecast_daily AS
SELECT
    wf.location_id,
    wf.forecast_date,
    wf.source,
    MIN(wf.temp_min_c) AS temp_min_c,
    MAX(wf.temp_max_c) AS temp_max_c,
    AVG(wf.temp_c) AS temp_avg_c,
    SUM(wf.precipitation_mm) AS precipitation_total_mm,
    MAX(wf.precipitation_prob_pct) AS max_precip_prob_pct,
    AVG(wf.humidity_pct) AS avg_humidity_pct,
    AVG(wf.wind_speed_kmh) AS avg_wind_speed_kmh,
    MAX(wf.wind_gust_kmh) AS max_wind_gust_kmh,
    MAX(wf.uv_index) AS max_uv_index,
    AVG(wf.solar_radiation_wm2) AS avg_solar_radiation_wm2,
    MAX(wf.et0_estimate_mm) AS et0_mm
FROM weather_forecast wf
GROUP BY wf.location_id, wf.forecast_date, wf.source;

-- Spray window view: days with suitable conditions for spraying
CREATE OR REPLACE VIEW v_spray_window AS
SELECT
    location_id,
    forecast_date,
    source,
    avg_wind_speed_kmh,
    max_precip_prob_pct,
    temp_avg_c,
    CASE
        WHEN avg_wind_speed_kmh < 15 AND max_precip_prob_pct < 30 AND temp_avg_c BETWEEN 5 AND 35
        THEN 'suitable'
        WHEN avg_wind_speed_kmh < 20 AND max_precip_prob_pct < 50 AND temp_avg_c BETWEEN 3 AND 38
        THEN 'marginal'
        ELSE 'unsuitable'
    END AS spray_suitability
FROM v_weather_forecast_daily
WHERE avg_wind_speed_kmh IS NOT NULL;

-- ============================================================
-- CROP GROWTH STAGE TRACKING
-- ============================================================

CREATE TABLE IF NOT EXISTS crop_growth_stage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_cycle_id UUID NOT NULL REFERENCES crop_cycle(id) ON DELETE CASCADE,
    stage_name VARCHAR(100) NOT NULL,
    stage_order INTEGER NOT NULL,
    expected_gdd NUMERIC(8,1),
    actual_gdd NUMERIC(8,1),
    expected_date DATE,
    actual_date DATE,
    gdd_accumulated_at_entry NUMERIC(8,1),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'current', 'completed', 'skipped')),
    detected_by VARCHAR(50) DEFAULT 'gdd' CHECK (detected_by IN ('gdd', 'manual', 'remote_sensing')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crop_growth_stage_cycle
    ON crop_growth_stage(crop_cycle_id, stage_order);

CREATE UNIQUE INDEX IF NOT EXISTS idx_crop_growth_stage_unique
    ON crop_growth_stage(crop_cycle_id, stage_name);

-- ============================================================
-- CROP GDD CONFIGURATION
-- ============================================================

CREATE TABLE IF NOT EXISTS crop_gdd_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_name VARCHAR(100) NOT NULL UNIQUE,
    base_temp_c NUMERIC(4,1) NOT NULL DEFAULT 10.0,
    upper_temp_c NUMERIC(4,1) NOT NULL DEFAULT 30.0,
    total_gdd_required NUMERIC(8,1),
    stages JSONB NOT NULL DEFAULT '[]',
    kc_values JSONB NOT NULL DEFAULT '{}',
    source VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- View: current growth stage per active crop cycle
CREATE OR REPLACE VIEW v_crop_current_stage AS
SELECT DISTINCT ON (cc.id)
    cc.id AS crop_cycle_id,
    cc.location_id,
    cc.plot_id,
    c.id AS crop_id,
    c.name AS crop_name,
    cc.planting_date,
    cc.season,
    cgs.stage_name AS current_stage,
    cgs.stage_order AS current_stage_order,
    cgs.actual_gdd,
    cgs.expected_gdd,
    cgs.expected_date AS current_stage_expected_date,
    cc.status AS cycle_status,
    cc.expected_harvest_date,
    CASE
        WHEN cgs.actual_gdd IS NULL THEN 'unknown'
        WHEN cgs.expected_gdd IS NULL THEN 'unknown'
        WHEN cgs.actual_gdd < cgs.expected_gdd * 0.8 THEN 'behind'
        WHEN cgs.actual_gdd > cgs.expected_gdd * 1.2 THEN 'ahead'
        ELSE 'on_track'
    END AS schedule_status,
    gdd.total_gdd_required AS crop_total_gdd,
    CASE
        WHEN gdd.total_gdd_required IS NOT NULL AND cgs.actual_gdd IS NOT NULL
        THEN ROUND((cgs.actual_gdd / gdd.total_gdd_required * 100)::numeric, 1)
        ELSE NULL
    END AS pct_gdd_complete
FROM crop_cycle cc
JOIN crop c ON c.id = cc.crop_id
LEFT JOIN LATERAL (
    SELECT * FROM crop_growth_stage
    WHERE crop_cycle_id = cc.id AND status = 'current'
    ORDER BY stage_order DESC LIMIT 1
) cgs ON TRUE
LEFT JOIN crop_gdd_config gdd ON gdd.crop_name = c.name
WHERE cc.status IN ('active', 'flowering');

-- View: upcoming growth stages for active crop cycles
CREATE OR REPLACE VIEW v_crop_upcoming_stages AS
SELECT
    cc.id AS crop_cycle_id,
    cc.location_id,
    c.name AS crop_name,
    cgs_next.stage_name AS next_stage,
    cgs_next.expected_gdd AS next_stage_gdd,
    cgs_next.expected_date AS next_stage_expected_date,
    cgs_cur.stage_name AS current_stage,
    cgs_cur.actual_gdd AS current_gdd,
    cgs_next.expected_gdd - cgs_cur.actual_gdd AS gdd_remaining
FROM crop_cycle cc
JOIN crop c ON c.id = cc.crop_id
LEFT JOIN LATERAL (
    SELECT * FROM crop_growth_stage
    WHERE crop_cycle_id = cc.id AND status = 'current'
    ORDER BY stage_order DESC LIMIT 1
) cgs_cur ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM crop_growth_stage
    WHERE crop_cycle_id = cc.id AND status = 'pending'
    ORDER BY stage_order ASC LIMIT 1
) cgs_next ON TRUE
WHERE cc.status IN ('active', 'flowering')
  AND cgs_next.id IS NOT NULL;

-- View: ET₀ summary for active crop cycles
CREATE OR REPLACE VIEW v_crop_water_balance AS
SELECT
    cc.id AS crop_cycle_id,
    cc.location_id,
    cc.plot_id,
    c.name AS crop_name,
    cc.planting_date,
    cgs.stage_name AS current_stage,
    COALESCE(wb.total_rainfall_mm, 0) AS period_rainfall_mm,
    COALESCE(wb.total_irrigation_mm, 0) AS period_irrigation_mm,
    COALESCE(wb.total_et0_mm, 0) AS period_et0_mm,
    COALESCE(wb.total_et0_mm, 0) - COALESCE(wb.total_rainfall_mm, 0) - COALESCE(wb.total_irrigation_mm, 0) AS water_deficit_mm,
    CASE
        WHEN COALESCE(wb.total_et0_mm, 0) = 0 THEN 'no_data'
        WHEN (COALESCE(wb.total_rainfall_mm, 0) + COALESCE(wb.total_irrigation_mm, 0)) < wb.total_et0_mm * 0.5 THEN 'stressed'
        WHEN (COALESCE(wb.total_rainfall_mm, 0) + COALESCE(wb.total_irrigation_mm, 0)) < wb.total_et0_mm * 0.8 THEN 'mild_stress'
        ELSE 'adequate'
    END AS water_status
FROM crop_cycle cc
JOIN crop c ON c.id = cc.crop_id
LEFT JOIN LATERAL (
    SELECT * FROM crop_growth_stage
    WHERE crop_cycle_id = cc.id AND status = 'current'
    LIMIT 1
) cgs ON TRUE
LEFT JOIN LATERAL (
    SELECT
        cc2.id AS cycle_id,
        SUM(wf.et0_estimate_mm) AS total_et0_mm,
        (SELECT SUM(w.precipitation_mm) FROM weather_observation w
         WHERE w.location_id = cc2.location_id
           AND w.observation_date BETWEEN cc2.planting_date AND CURRENT_DATE) AS total_rainfall_mm,
        (SELECT SUM(rc.irrigation_mm_used) FROM resource_consumption rc
         WHERE rc.location_id = cc2.location_id
           AND rc.period_start >= cc2.planting_date) AS total_irrigation_mm
    FROM crop_cycle cc2
    LEFT JOIN weather_forecast wf ON wf.location_id = cc2.location_id
        AND wf.forecast_date BETWEEN cc2.planting_date AND CURRENT_DATE
    WHERE cc2.id = cc.id
    GROUP BY cc2.id, cc2.location_id, cc2.planting_date
) wb ON TRUE
WHERE cc.status IN ('active', 'flowering');

COMMIT;
