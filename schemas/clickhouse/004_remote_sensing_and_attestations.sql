-- ============================================================
-- ClickHouse: Remote sensing observations
-- ============================================================

CREATE TABLE IF NOT EXISTS remote_sensing_events
(
    timestamp DateTime64(3),
    observation_id UUID,
    location_id UUID,
    plot_id Nullable(UUID),
    source LowCardinality(String),
    ndvi Nullable(Float64),
    ndre Nullable(Float64),
    evi Nullable(Float64),
    savi Nullable(Float64),
    canopy_cover_pct Nullable(Float64),
    canopy_height_m Nullable(Float64),
    ndwi Nullable(Float64),
    cloud_cover_pct Nullable(Float64),
    metadata Map(String, String),
    _inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (location_id, source, timestamp)
TTL toDateTime(timestamp) + INTERVAL 2 YEAR;

-- ============================================================
-- ClickHouse: Attestation events
-- ============================================================

CREATE TABLE IF NOT EXISTS attestation_events
(
    timestamp DateTime64(3),
    attestation_uid String,
    schema_uid Nullable(String),
    chain LowCardinality(String),
    attester Nullable(String),
    recipient Nullable(String),
    subject_type LowCardinality(String),
    status LowCardinality(String),
    revoked Bool DEFAULT false,
    metadata Map(String, String),
    _inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (chain, attestation_uid)
TTL toDateTime(timestamp) + INTERVAL 2 YEAR;
