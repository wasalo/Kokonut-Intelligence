-- ============================================================
-- KGP Deployment Tracking
-- Records deployed KGP contract addresses per chain.
-- ============================================================

CREATE TABLE IF NOT EXISTS kgp_protocol_deployment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain VARCHAR(50) NOT NULL,
    deployer_address VARCHAR(42) NOT NULL,
    deployed_contracts JSONB NOT NULL DEFAULT '{}',
    multisig_address VARCHAR(42),
    status VARCHAR(50) DEFAULT 'deployed',
    deployed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_kgp_deployment_status CHECK (status IN (
        'deployed', 'ownership_transferred', 'deprecated'
    ))
);

CREATE INDEX IF NOT EXISTS idx_kgp_deploy_chain ON kgp_protocol_deployment(chain);
CREATE INDEX IF NOT EXISTS idx_kgp_deploy_status ON kgp_protocol_deployment(status);
