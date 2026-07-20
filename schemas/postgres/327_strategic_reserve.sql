-- Strategic Reserve layer for the Kokonut ecosystem.
-- Unifies existing reserve-shaped primitives (carbon buffer pool, commons
-- reserve_allocation_pct, funding_round totals, strategy_contingency) into a
-- first-class, monitorable reserve registry. Supports resilience reporting and
-- a fundability/due-diligence signal (the energy-reserve "investment
-- incentive" parallel from the strategic-reserve literature).
--
-- Read-only analytics and a human-approved release proposal path only.
-- NO automatic on-chain drawdown: release decisions route through
-- decision_policy.requires_approval / agents/safety.py.
--
-- Idempotent: safe to re-run and extend.
-- Seed data lives in schemas/seeds/115_strategic_reserve.sql.

CREATE TABLE IF NOT EXISTS strategic_reserve (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reserve_code VARCHAR(100) NOT NULL UNIQUE,
    reserve_type VARCHAR(50) NOT NULL,     -- carbon_buffer, commons_reserve,
                                                 -- financial_ringfence, capability_standby, seed_vault
    entity_scope VARCHAR(50) NOT NULL,    -- farm, guild, dao, network
    scope_id UUID,                          -- location/guild/dao id when scope is not network
    name VARCHAR(255) NOT NULL,
    description TEXT,
    held_quantity NUMERIC(18,6) NOT NULL DEFAULT 0,
    capacity_target NUMERIC(18,6) NOT NULL DEFAULT 0,
    unit VARCHAR(50) NOT NULL DEFAULT 'usd',
    refill_policy VARCHAR(100),               -- fixed, percentage, event_driven, none
    trigger_metric_key VARCHAR(100),         -- metric_value key that gates release
    trigger_operator VARCHAR(20),           -- lt, lte, gt, gte, eq, between
    trigger_threshold NUMERIC(18,6),
    status VARCHAR(50) DEFAULT 'active',    -- draft, active, depleted, paused, retired
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    CHECK (reserve_type IN (
        'carbon_buffer', 'commons_reserve', 'financial_ringfence',
        'capability_standby', 'seed_vault')),
    CHECK (entity_scope IN ('farm', 'guild', 'dao', 'network')),
    CHECK (status IN ('draft', 'active', 'depleted', 'paused', 'retired')),
    CHECK (trigger_operator IS NULL OR trigger_operator IN ('lt', 'lte', 'gt', 'gte', 'eq', 'between'))
);

CREATE INDEX IF NOT EXISTS idx_strategic_reserve_type ON strategic_reserve (reserve_type);
CREATE INDEX IF NOT EXISTS idx_strategic_reserve_scope ON strategic_reserve (entity_scope, scope_id);
CREATE INDEX IF NOT EXISTS idx_strategic_reserve_status ON strategic_reserve (status);

-- Release events are PROPOSED by the monitor and require human approval
-- before any governed write. Mirrors the 5-state process_model vocabulary.
CREATE TABLE IF NOT EXISTS strategic_reserve_release (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reserve_id UUID NOT NULL REFERENCES strategic_reserve(id) ON DELETE CASCADE,
    proposed_quantity NUMERIC(18,6) NOT NULL DEFAULT 0,
    reason TEXT,
    trigger_metric_value NUMERIC(18,6),
    status VARCHAR(50) DEFAULT 'draft',    -- draft, submitted, verified, executed, rejected
    approved_by UUID,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    metadata JSONB DEFAULT '{}',
    CHECK (status IN ('draft', 'submitted', 'verified', 'executed', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_reserve_release_reserve ON strategic_reserve_release (reserve_id);
CREATE INDEX IF NOT EXISTS idx_reserve_release_status ON strategic_reserve_release (status);
