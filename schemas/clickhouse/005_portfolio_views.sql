-- ============================================================
-- ClickHouse: Portfolio evaluation views
-- ============================================================

-- Current platform activity by location from analytical event mirrors.
CREATE VIEW IF NOT EXISTS v_portfolio_location_activity AS
SELECT
    location_id,
    min(day) AS first_event_date,
    max(day) AS latest_event_date,
    sum(event_count) AS event_count,
    uniqExact(event_source) AS source_count,
    groupUniqArray(event_source) AS event_sources
FROM
(
    SELECT toDate(timestamp) AS day, location_id, count() AS event_count, 'events_raw' AS event_source
    FROM events_raw
    GROUP BY day, location_id

    UNION ALL

    SELECT toDate(timestamp) AS day, location_id, count() AS event_count, 'financial_events' AS event_source
    FROM financial_events
    GROUP BY day, location_id

    UNION ALL

    SELECT toDate(timestamp) AS day, location_id, count() AS event_count, 'sensor_readings' AS event_source
    FROM sensor_readings
    GROUP BY day, location_id

    UNION ALL

    SELECT toDate(timestamp) AS day, location_id, count() AS event_count, 'weather_events' AS event_source
    FROM weather_events
    GROUP BY day, location_id

    UNION ALL

    SELECT toDate(timestamp) AS day, ifNull(location_id, toUUID('00000000-0000-0000-0000-000000000000')) AS location_id, count() AS event_count, 'dlego_events' AS event_source
    FROM dlego_events
    GROUP BY day, location_id
)
GROUP BY location_id;

-- Monthly portfolio value flow and data completeness signals.
CREATE VIEW IF NOT EXISTS v_portfolio_monthly_evaluation AS
SELECT
    month,
    location_id,
    revenue_usd,
    expense_usd,
    revenue_usd - expense_usd AS net_value_usd,
    financial_event_count,
    sensor_reading_count,
    weather_event_count,
    web3_event_count,
    generic_event_count,
    (financial_event_count > 0) + (sensor_reading_count > 0) + (weather_event_count > 0) + (web3_event_count > 0) + (generic_event_count > 0) AS data_channel_count
FROM
(
    SELECT
        month,
        location_id,
        sum(revenue_usd) AS revenue_usd,
        sum(expense_usd) AS expense_usd,
        sum(financial_event_count) AS financial_event_count,
        sum(sensor_reading_count) AS sensor_reading_count,
        sum(weather_event_count) AS weather_event_count,
        sum(web3_event_count) AS web3_event_count,
        sum(generic_event_count) AS generic_event_count
    FROM
    (
        SELECT
            toStartOfMonth(timestamp) AS month,
            location_id,
            sumIf(toFloat64(ifNull(amount_usd, amount)), transaction_type IN ('revenue', 'sale')) AS revenue_usd,
            sumIf(toFloat64(ifNull(amount_usd, amount)), transaction_type = 'expense') AS expense_usd,
            count() AS financial_event_count,
            0 AS sensor_reading_count,
            0 AS weather_event_count,
            0 AS web3_event_count,
            0 AS generic_event_count
        FROM financial_events
        GROUP BY month, location_id

        UNION ALL

        SELECT toStartOfMonth(timestamp) AS month, location_id, 0, 0, 0, count(), 0, 0, 0
        FROM sensor_readings
        GROUP BY month, location_id

        UNION ALL

        SELECT toStartOfMonth(timestamp) AS month, location_id, 0, 0, 0, 0, count(), 0, 0
        FROM weather_events
        GROUP BY month, location_id

        UNION ALL

        SELECT toStartOfMonth(timestamp) AS month, ifNull(location_id, toUUID('00000000-0000-0000-0000-000000000000')) AS location_id, 0, 0, 0, 0, 0, count(), 0
        FROM dlego_events
        GROUP BY month, location_id

        UNION ALL

        SELECT toStartOfMonth(timestamp) AS month, location_id, 0, 0, 0, 0, 0, 0, count()
        FROM events_raw
        GROUP BY month, location_id
    )
    GROUP BY month, location_id
)
;

-- Portfolio-level summary for Green Paper evidence maturity discussions.
CREATE VIEW IF NOT EXISTS v_portfolio_evaluation_summary AS
SELECT
    countDistinct(location_id) AS location_count,
    sum(event_count) AS event_count,
    avg(source_count) AS avg_source_count,
    countIf(source_count >= 3) AS locations_with_three_or_more_sources,
    max(latest_event_date) AS latest_event_date
FROM v_portfolio_location_activity
WHERE location_id != toUUID('00000000-0000-0000-0000-000000000000');
