-- ============================================================
-- ClickHouse: Telemetry infrastructure sync
-- Adds missing columns to remote_sensing_events and creates
-- materialized view for daily RS summaries.
-- ============================================================

-- Add missing columns to remote_sensing_events
-- (ClickHouse supports ALTER TABLE ... ADD COLUMN IF NOT EXISTS)
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS msavi Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS satvi Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS bsi Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS nbr2 Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS ndti Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS lswi Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS brightness_index Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS tc_brightness Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS tc_greenness Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS tc_wetness Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS band_blue Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS band_green Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS band_red Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS band_nir Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS band_swir1 Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS band_swir2 Nullable(Float64);
ALTER TABLE remote_sensing_events ADD COLUMN IF NOT EXISTS source_system LowCardinality(String) DEFAULT 'csv_upload';

-- Daily remote sensing summary materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_remote_sensing_summary
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (location_id, source, day)
AS
SELECT
    toDate(timestamp) AS day,
    location_id,
    source,
    avg(ndvi) AS avg_ndvi,
    avg(ndre) AS avg_ndre,
    avg(evi) AS avg_evi,
    avg(savi) AS avg_savi,
    avg(msavi) AS avg_msavi,
    avg(ndwi) AS avg_ndwi,
    avg(cloud_cover_pct) AS avg_cloud_cover,
    count() AS observation_count,
    min(cloud_cover_pct) AS min_cloud_cover,
    max(cloud_cover_pct) AS max_cloud_cover
FROM remote_sensing_events
GROUP BY day, location_id, source;

-- Remote sensing freshness view
CREATE OR REPLACE VIEW v_remote_sensing_freshness AS
SELECT
    location_id,
    source,
    max(timestamp) AS last_observation_at,
    dateDiff('hour', max(timestamp), now()) AS hours_since_last,
    count() AS total_observations
FROM remote_sensing_events
GROUP BY location_id, source
ORDER BY last_observation_at DESC;
