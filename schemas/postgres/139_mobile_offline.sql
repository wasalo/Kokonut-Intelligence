-- ============================================================
-- Mobile / Offline Data Collection
-- Offline-first data collection with sync, device tracking,
-- and conflict resolution for field workers.
-- ============================================================

-- Mobile device registration
CREATE TABLE IF NOT EXISTS mobile_device (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id       VARCHAR(200) NOT NULL UNIQUE,
    device_name     VARCHAR(300),
    device_type     VARCHAR(100) DEFAULT 'phone',
    os              VARCHAR(100),
    os_version      VARCHAR(50),
    app_version     VARCHAR(50),
    push_token      TEXT,
    location_id     UUID REFERENCES location(id),
    user_id         VARCHAR(200),

    -- Capability flags
    has_camera      BOOLEAN DEFAULT TRUE,
    has_gps         BOOLEAN DEFAULT TRUE,
    has_offline     BOOLEAN DEFAULT TRUE,

    -- Status
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    last_sync_at    TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mobile_device_user ON mobile_device (user_id);
CREATE INDEX IF NOT EXISTS idx_mobile_device_location ON mobile_device (location_id);

-- Offline data collection queue (pending sync)
CREATE TABLE IF NOT EXISTS offline_collection (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id       VARCHAR(200) NOT NULL,
    user_id         VARCHAR(200),
    location_id     UUID REFERENCES location(id),

    -- Collection details
    collection_type VARCHAR(100) NOT NULL,
    form_id         VARCHAR(200),
    form_version    VARCHAR(50),

    -- Data payload
    payload         JSONB NOT NULL DEFAULT '{}',
    photo_refs      JSONB DEFAULT '[]',

    -- GPS at collection
    latitude        NUMERIC(10,7),
    longitude       NUMERIC(10,7),
    accuracy_m      NUMERIC(8,2),

    -- Timestamps
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    synced_at       TIMESTAMPTZ,
    sync_status     VARCHAR(50) NOT NULL DEFAULT 'pending',
    sync_error      TEXT,

    -- Conflict resolution
    client_id       VARCHAR(200),
    server_version  INTEGER DEFAULT 0,
    conflict_flag   BOOLEAN DEFAULT FALSE,
    resolved_by     VARCHAR(200),

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_offline_collection_device ON offline_collection (device_id);
CREATE INDEX IF NOT EXISTS idx_offline_collection_sync ON offline_collection (sync_status);
CREATE INDEX IF NOT EXISTS idx_offline_collection_user ON offline_collection (user_id);
CREATE INDEX IF NOT EXISTS idx_offline_collection_location ON offline_collection (location_id);
CREATE INDEX IF NOT EXISTS idx_offline_collection_type ON offline_collection (collection_type);

-- Sync log (audit trail)
CREATE TABLE IF NOT EXISTS sync_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id       VARCHAR(200) NOT NULL,
    collection_id   UUID REFERENCES offline_collection(id),
    sync_action     VARCHAR(50) NOT NULL,
    direction       VARCHAR(20) NOT NULL DEFAULT 'push',
    status          VARCHAR(50) NOT NULL DEFAULT 'success',
    records_synced  INTEGER DEFAULT 0,
    conflict_count  INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_log_device ON sync_log (device_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_created ON sync_log (created_at);

-- Form definitions (offline-capable)
CREATE TABLE IF NOT EXISTS mobile_form (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id         VARCHAR(200) NOT NULL UNIQUE,
    name            VARCHAR(300) NOT NULL,
    description     TEXT,
    form_schema     JSONB NOT NULL DEFAULT '{}',
    ui_schema       JSONB DEFAULT '{}',
    version         VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    collection_type VARCHAR(100) NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    location_id     UUID REFERENCES location(id),
    min_app_version VARCHAR(50),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Public Views
-- ============================================================

CREATE OR REPLACE VIEW v_offline_sync_status AS
SELECT
    oc.device_id,
    md.device_name,
    md.user_id,
    oc.collection_type,
    COUNT(*) AS pending_count,
    MIN(oc.collected_at) AS oldest_pending,
    MAX(oc.collected_at) AS newest_pending
FROM offline_collection oc
LEFT JOIN mobile_device md ON md.device_id = oc.device_id
WHERE oc.sync_status = 'pending'
GROUP BY oc.device_id, md.device_name, md.user_id, oc.collection_type
ORDER BY oldest_pending;

CREATE OR REPLACE VIEW v_sync_performance AS
SELECT
    sl.device_id,
    sl.sync_action,
    DATE(sl.created_at) AS sync_date,
    COUNT(*) AS sync_count,
    SUM(sl.records_synced) AS total_records,
    SUM(sl.conflict_count) AS total_conflicts,
    AVG(sl.duration_ms) AS avg_duration_ms,
    SUM(CASE WHEN sl.status = 'error' THEN 1 ELSE 0 END) AS error_count
FROM sync_log sl
WHERE sl.created_at >= NOW() - INTERVAL '30 days'
GROUP BY sl.device_id, sl.sync_action, DATE(sl.created_at)
ORDER BY sync_date DESC;

CREATE OR REPLACE VIEW v_mobile_device_health AS
SELECT
    md.id,
    md.device_id,
    md.device_name,
    md.user_id,
    md.app_version,
    md.last_sync_at,
    md.last_seen_at,
    EXTRACT(EPOCH FROM (NOW() - md.last_sync_at)) / 3600 AS hours_since_sync,
    (SELECT COUNT(*) FROM offline_collection oc WHERE oc.device_id = md.device_id AND oc.sync_status = 'pending') AS pending_records,
    (SELECT COUNT(*) FROM sync_log sl WHERE sl.device_id = md.device_id AND sl.status = 'error' AND sl.created_at >= NOW() - INTERVAL '7 days') AS errors_7d,
    md.status
FROM mobile_device md
ORDER BY md.last_seen_at DESC NULLS LAST;
