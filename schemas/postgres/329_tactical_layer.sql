-- Tactical Layer: a single agent-safe store for DRAFT "tactical opportunities"
-- surfaced by the chess-tactic-inspired detectors (fork, discovered double-check,
-- pin/dependency, zwischenzug, promotion-block). Each detector writes only
-- status='draft'; a human promotes/acts via a separate governed flow. No
-- autonomous action, publish, or on-chain effect.
--
-- Idempotent: safe to re-run and extend.

CREATE TABLE IF NOT EXISTS tactical_opportunity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_type VARCHAR(30) NOT NULL
        CHECK (opportunity_type IN ('fork', 'double_check', 'pin', 'zwischenzug', 'promotion_block')),
    location_id UUID,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    opportunity_summary TEXT NOT NULL,
    source_refs JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'rejected')),
    proposed_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (location_id IS NOT NULL OR source_refs IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_tactical_opportunity_location
    ON tactical_opportunity (location_id);
CREATE INDEX IF NOT EXISTS idx_tactical_opportunity_type
    ON tactical_opportunity (opportunity_type, status);
CREATE INDEX IF NOT EXISTS idx_tactical_opportunity_status
    ON tactical_opportunity (status) WHERE status = 'draft';
