-- State of Kokonut: ecosystem funding + actor participation model.
-- Supports the network/ecosystem-level "State of Kokonut" report (funding raised,
-- funding sources, and which ecosystem actor -- Network / DAO / Foundation /
-- Genesis / Seeds -- decided to fund or participate in a project).
--
-- Idempotent: safe to re-run and to extend with additional rounds/participation.
-- Seed data lives in schemas/seeds/114_state_of_kokonut_funding.sql.

CREATE TABLE IF NOT EXISTS funding_round (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    round_code VARCHAR(100) NOT NULL UNIQUE,
    actor_type VARCHAR(50) NOT NULL,           -- network, dao, foundation, genesis, seeds
    actor_name VARCHAR(255) NOT NULL,
    round_name VARCHAR(255) NOT NULL,
    raised_amount NUMERIC(18,6) NOT NULL DEFAULT 0,
    currency VARCHAR(20) NOT NULL DEFAULT 'USD',
    source_type VARCHAR(100),                  -- grants, token_sale, equity, donation, revenue, other
    source_detail TEXT,
    period_start DATE,
    period_end DATE,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'closed',       -- planned, open, closed, cancelled
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (actor_type IN ('network', 'dao', 'foundation', 'genesis', 'seeds'))
);

CREATE INDEX IF NOT EXISTS idx_funding_round_actor ON funding_round (actor_type);
CREATE INDEX IF NOT EXISTS idx_funding_round_period ON funding_round (period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_funding_round_location ON funding_round (location_id);

CREATE TABLE IF NOT EXISTS project_funding (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    funding_round_id UUID NOT NULL REFERENCES funding_round(id) ON DELETE CASCADE,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    dao_proposal_id UUID REFERENCES dao_proposal(id) ON DELETE SET NULL,
    guild_id UUID REFERENCES kokonut_guild(id) ON DELETE SET NULL,
    actor_type VARCHAR(50) NOT NULL,           -- network, dao, foundation, genesis, seeds
    amount NUMERIC(18,6) NOT NULL DEFAULT 0,
    token VARCHAR(50),
    decision_status VARCHAR(50) DEFAULT 'proposed', -- proposed, approved, rejected, executed
    decided_at DATE,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (actor_type IN ('network', 'dao', 'foundation', 'genesis', 'seeds')),
    CHECK (decision_status IN ('proposed', 'approved', 'rejected', 'executed'))
);

CREATE INDEX IF NOT EXISTS idx_project_funding_round ON project_funding (funding_round_id);
CREATE INDEX IF NOT EXISTS idx_project_funding_location ON project_funding (location_id);
CREATE INDEX IF NOT EXISTS idx_project_funding_actor ON project_funding (actor_type);
CREATE INDEX IF NOT EXISTS idx_project_funding_proposal ON project_funding (dao_proposal_id);
