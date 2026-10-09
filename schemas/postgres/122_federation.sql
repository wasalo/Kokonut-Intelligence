-- ============================================================
-- 122_federation.sql — Inter-farm communication protocol
-- ============================================================

CREATE TABLE IF NOT EXISTS federation_node (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_name VARCHAR(100) NOT NULL UNIQUE,
    node_url VARCHAR(200) NOT NULL,
    node_public_key TEXT,
    trust_level VARCHAR(20) NOT NULL DEFAULT 'untrusted'
        CHECK (trust_level IN ('untrusted', 'peer', 'trusted', 'verified')),
    shared_capabilities JSONB DEFAULT '[]',
    last_sync_at TIMESTAMPTZ,
    sync_interval_seconds INTEGER DEFAULT 3600,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'suspended', 'offline')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_federation_node_trust
    ON federation_node (trust_level, status);
CREATE INDEX IF NOT EXISTS idx_federation_node_url
    ON federation_node (node_url);

CREATE TABLE IF NOT EXISTS federation_share (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id UUID NOT NULL REFERENCES federation_node(id) ON DELETE CASCADE,
    data_type VARCHAR(100) NOT NULL,
    aggregate_data JSONB NOT NULL,
    period_start DATE,
    period_end DATE,
    consent_level VARCHAR(20) NOT NULL DEFAULT 'aggregate'
        CHECK (consent_level IN ('none', 'aggregate', 'detailed')),
    shared_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    verified BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_federation_share_source
    ON federation_share (source_node_id, data_type, shared_at DESC);
CREATE INDEX IF NOT EXISTS idx_federation_share_type
    ON federation_share (data_type, period_start, period_end);

CREATE TABLE IF NOT EXISTS federation_query (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_type VARCHAR(100) NOT NULL,
    parameters JSONB DEFAULT '{}',
    requesting_node_id UUID REFERENCES federation_node(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_federation_query_status
    ON federation_query (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_federation_query_type
    ON federation_query (query_type, created_at DESC);
