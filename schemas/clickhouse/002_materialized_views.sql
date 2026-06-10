-- ============================================================
-- ClickHouse: Materialized views for pre-aggregated analytics
-- ============================================================

-- Daily event counts by type and source
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_event_counts
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (day, event_type, source)
AS SELECT
    toDate(timestamp) AS day,
    event_type,
    source,
    count() AS event_count
FROM events_raw
GROUP BY day, event_type, source;

-- Hourly sensor aggregates
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_sensor_stats
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (sensor_id, hour)
AS SELECT
    sensor_id,
    toStartOfHour(timestamp) AS hour,
    avgState(value) AS avg_value,
    minState(value) AS min_value,
    maxState(value) AS max_value,
    countState() AS reading_count
FROM sensor_readings
GROUP BY sensor_id, hour;

-- Daily wallet activity summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_wallet_activity
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (day, chain, event_type)
AS SELECT
    toDate(timestamp) AS day,
    chain,
    event_type,
    count() AS tx_count,
    sum(toFloat64(value)) AS total_value
FROM wallet_events
GROUP BY day, chain, event_type;

-- Monthly financial summary by location
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_financial_summary
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(month)
ORDER BY (month, location_id, transaction_type)
AS SELECT
    toStartOfMonth(timestamp) AS month,
    location_id,
    transaction_type,
    sum(toFloat64(amount)) AS total_amount,
    count() AS transaction_count
FROM financial_events
GROUP BY month, location_id, transaction_type;

-- Daily weather summary by location
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_weather_summary
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (location_id, day)
AS SELECT
    location_id,
    toDate(timestamp) AS day,
    avgState(temperature_c) AS avg_temp,
    maxState(temperature_c) AS max_temp,
    minState(temperature_c) AS min_temp,
    sumState(precipitation_mm) AS total_precip,
    avgState(humidity_pct) AS avg_humidity
FROM weather_events
GROUP BY location_id, day;
