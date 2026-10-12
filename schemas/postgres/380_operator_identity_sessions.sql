-- Browser operator identity is separate from API keys, capability tokens,
-- and Directus accounts. An OIDC login is not authorization: identities must
-- be provisioned and receive explicit location-scoped grants.
CREATE TABLE IF NOT EXISTS operator_identity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    display_name TEXT,
    email TEXT,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (issuer, subject)
);

CREATE TABLE IF NOT EXISTS operator_scope_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operator_identity(id),
    resource TEXT NOT NULL CHECK (resource ~ '^[a-z][a-z0-9_]*$'),
    action TEXT NOT NULL CHECK (action ~ '^[a-z][a-z0-9_]*$'),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    granted_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    UNIQUE (operator_id, resource, action, location_id, created_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_operator_scope_grant_active
    ON operator_scope_grant (operator_id, resource, action, location_id)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS operator_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operator_identity(id),
    session_token_hash CHAR(64) NOT NULL UNIQUE,
    csrf_token_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_operator_session_active
    ON operator_session (session_token_hash, expires_at)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_operator_session_operator
    ON operator_session (operator_id, expires_at DESC);
