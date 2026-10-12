-- Correctness-first read interfaces over retained raw data.
-- Legacy materialized views remain unchanged for rollback; these need no backfill.
CREATE VIEW IF NOT EXISTS v_monthly_wallet_unique_active_v2 AS
SELECT toStartOfMonth(timestamp) AS month, chain,
    uniqExact(wallet_address) AS unique_wallets, count() AS total_events
FROM wallet_events GROUP BY month, chain;

CREATE VIEW IF NOT EXISTS v_daily_dlego_protocol_usage_v2 AS
SELECT toDate(timestamp) AS day, protocol_id, action_type, chain,
    count() AS action_count, sum(amount) AS total_amount
FROM dlego_events GROUP BY day, protocol_id, action_type, chain;

CREATE VIEW IF NOT EXISTS v_dlego_value_by_location_v2 AS
SELECT toStartOfMonth(timestamp) AS month,
    ifNull(location_id, toUUID('00000000-0000-0000-0000-000000000000')) AS location_id,
    protocol_id, sum(amount) AS total_value, count() AS usage_count
FROM dlego_events GROUP BY month, location_id, protocol_id;

CREATE VIEW IF NOT EXISTS v_daily_remote_sensing_summary_v2 AS
SELECT toDate(timestamp) AS day, location_id, source,
    avg(ndvi) AS avg_ndvi, avg(ndre) AS avg_ndre, avg(evi) AS avg_evi,
    avg(savi) AS avg_savi, avg(msavi) AS avg_msavi, avg(ndwi) AS avg_ndwi,
    avg(cloud_cover_pct) AS avg_cloud_cover, count() AS observation_count,
    min(cloud_cover_pct) AS min_cloud_cover, max(cloud_cover_pct) AS max_cloud_cover
FROM remote_sensing_events GROUP BY day, location_id, source;
