-- ============================================================
-- ClickHouse: Event tables for analytics
-- ============================================================

-- Raw events (time-series)
CREATE TABLE IF NOT EXISTS events_raw
(
    timestamp DateTime64(3),
    event_type LowCardinality(String),
    source LowCardinality(String),
    location_id UUID,
    plot_id Nullable(UUID),
    crop_cycle_id Nullable(UUID),
    entity_id UUID,
    entity_type LowCardinality(String),
    action LowCardinality(String),
    payload String,
    metadata Map(String, String),
    _inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event_type, source, timestamp)
TTL toDateTime(timestamp) + INTERVAL 2 YEAR
SETTINGS index_granularity = 8192;

-- Wallet activity events
CREATE TABLE IF NOT EXISTS wallet_events
(
    timestamp DateTime64(3),
    wallet_address String,
    chain LowCardinality(String),
    tx_hash String,
    block_number UInt64,
    event_type LowCardinality(String),
    from_address Nullable(String),
    to_address Nullable(String),
    contract_address Nullable(String),
    value Decimal128(8),
    token LowCardinality(Nullable(String)),
    token_amount Decimal128(8),
    gas_used UInt64,
    status LowCardinality(String),
    metadata Map(String, String),
    _inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (chain, wallet_address, timestamp)
TTL toDateTime(timestamp) + INTERVAL 2 YEAR;

-- Sensor readings (time-series)
CREATE TABLE IF NOT EXISTS sensor_readings
(
    timestamp DateTime64(3),
    sensor_id String,
    sensor_type LowCardinality(String),
    location_id UUID,
    plot_id Nullable(UUID),
    value Float64,
    unit LowCardinality(String),
    quality LowCardinality(String),
    metadata Map(String, String),
    _inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (sensor_id, timestamp)
TTL toDateTime(timestamp) + INTERVAL 1 YEAR;

-- Weather observations
CREATE TABLE IF NOT EXISTS weather_events
(
    timestamp DateTime64(3),
    location_id UUID,
    source LowCardinality(String),
    temperature_c Nullable(Float64),
    precipitation_mm Nullable(Float64),
    humidity_pct Nullable(Float64),
    wind_speed_kmh Nullable(Float64),
    solar_radiation_wm2 Nullable(Float64),
    cloud_cover_pct Nullable(Float64),
    metadata Map(String, String),
    _inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (location_id, timestamp)
TTL toDateTime(timestamp) + INTERVAL 2 YEAR;

-- Financial transactions (analytical mirror)
CREATE TABLE IF NOT EXISTS financial_events
(
    timestamp DateTime64(3),
    transaction_id UUID,
    location_id UUID,
    transaction_type LowCardinality(String),
    category LowCardinality(Nullable(String)),
    amount Decimal128(2),
    currency LowCardinality(String),
    amount_usd Nullable(Decimal128(2)),
    chain LowCardinality(Nullable(String)),
    token LowCardinality(Nullable(String)),
    metadata Map(String, String),
    _inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (location_id, transaction_type, timestamp);

-- Digital Lego usage events
CREATE TABLE IF NOT EXISTS dlego_events
(
    timestamp DateTime64(3),
    wallet_id Nullable(UUID),
    protocol_id UUID,
    location_id Nullable(UUID),
    action_type LowCardinality(String),
    amount Nullable(Decimal128(8)),
    token LowCardinality(Nullable(String)),
    chain LowCardinality(String),
    tx_hash Nullable(String),
    metadata Map(String, String),
    _inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (protocol_id, timestamp);
