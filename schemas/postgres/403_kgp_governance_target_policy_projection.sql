-- ============================================================
-- 403_kgp_governance_target_policy_projection.sql
-- Materialize read-only target-policy state from Guild governance events.
-- ============================================================

CREATE TABLE IF NOT EXISTS kgp_governance_target_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id UUID NOT NULL REFERENCES kgp_protocol_deployment(id) ON DELETE CASCADE,
    permission_kind VARCHAR(30) NOT NULL
        CHECK (permission_kind IN ('target', 'selector', 'guild_scope')),
    target_address VARCHAR(42) NOT NULL
        CHECK (target_address ~ '^0x[0-9a-fA-F]{40}$'),
    selector VARCHAR(10) NOT NULL DEFAULT '',
    permission_value BOOLEAN NOT NULL,
    source_chain_event_id UUID NOT NULL
        REFERENCES kgp_chain_event(id) ON DELETE CASCADE,
    chain_projection BOOLEAN NOT NULL DEFAULT TRUE,
    orphaned_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (permission_kind = 'selector' AND selector ~ '^0x[0-9a-fA-F]{8}$') OR
        (permission_kind <> 'selector' AND selector = '')
    ),
    UNIQUE (deployment_id, permission_kind, target_address, selector)
);

CREATE INDEX IF NOT EXISTS idx_kgp_target_policy_source_event
    ON kgp_governance_target_policy(source_chain_event_id);

COMMENT ON TABLE kgp_governance_target_policy IS
    'Read-only current-state projection of Guild governance target policy; chain events remain the audit source.';
