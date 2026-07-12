-- ============================================================
-- 121_capability_tokens.sql — Zero-trust capability-based access
-- ============================================================

CREATE TABLE IF NOT EXISTS capability_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    holder VARCHAR(100) NOT NULL,
    capabilities JSONB NOT NULL DEFAULT '[]',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    max_usage INTEGER,
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_by VARCHAR(100),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_capability_token_hash
    ON capability_token (token_hash);
CREATE INDEX IF NOT EXISTS idx_capability_token_holder
    ON capability_token (holder, expires_at);
CREATE INDEX IF NOT EXISTS idx_capability_token_active
    ON capability_token (expires_at) WHERE NOT revoked;

CREATE TABLE IF NOT EXISTS access_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caller VARCHAR(100) NOT NULL,
    capability_token_id UUID,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    action VARCHAR(50) NOT NULL
        CHECK (action IN ('read', 'write', 'attest', 'publish', 'delete', 'admin')),
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('allowed', 'denied', 'expired', 'revoked')),
    ip_address INET,
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_access_audit_caller
    ON access_audit_log (caller, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_audit_resource
    ON access_audit_log (resource_type, resource_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_audit_time
    ON access_audit_log (created_at DESC);
