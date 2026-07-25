-- ============================================================
-- KGP Deployment Tracking
-- Records deployed KGP contract addresses per chain.
-- Table created by 317; add chain column + indexes.
-- ============================================================

ALTER TABLE kgp_protocol_deployment
    ADD COLUMN IF NOT EXISTS chain VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_kgp_deploy_chain ON kgp_protocol_deployment(chain);
CREATE INDEX IF NOT EXISTS idx_kgp_deploy_status ON kgp_protocol_deployment(status);
