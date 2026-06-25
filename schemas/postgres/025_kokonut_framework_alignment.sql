-- ============================================================
-- 025_kokonut_framework_alignment.sql — Knowledge Base alignment
-- ============================================================

-- The Baserow migration introduced some of these tables directly in older
-- runtimes. Keep this layer additive so clean rebuilds and migrated DBs converge.

-- Framework and impact reference tables
CREATE TABLE IF NOT EXISTS impact_framework (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE impact_framework ADD COLUMN IF NOT EXISTS framework_key VARCHAR(100);
ALTER TABLE impact_framework ADD COLUMN IF NOT EXISTS framework_type VARCHAR(100);
ALTER TABLE impact_framework ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active';
ALTER TABLE impact_framework ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'impact_framework_framework_key_key'
    ) THEN
        ALTER TABLE impact_framework ADD CONSTRAINT impact_framework_framework_key_key UNIQUE (framework_key);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS impact_dimension (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    framework_id UUID REFERENCES impact_framework(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE impact_dimension ADD COLUMN IF NOT EXISTS dimension_key VARCHAR(100);
ALTER TABLE impact_dimension ADD COLUMN IF NOT EXISTS dimension_type VARCHAR(100);
ALTER TABLE impact_dimension ADD COLUMN IF NOT EXISTS sort_order INTEGER;
ALTER TABLE impact_dimension ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'impact_dimension_dimension_key_key'
    ) THEN
        ALTER TABLE impact_dimension ADD CONSTRAINT impact_dimension_dimension_key_key UNIQUE (dimension_key);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS sdg (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE sdg ADD COLUMN IF NOT EXISTS sdg_number INTEGER;
ALTER TABLE sdg ADD COLUMN IF NOT EXISTS short_name VARCHAR(255);
ALTER TABLE sdg ADD COLUMN IF NOT EXISTS evidence_maturity VARCHAR(100);
ALTER TABLE sdg ADD COLUMN IF NOT EXISTS tier VARCHAR(50);
ALTER TABLE sdg ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'sdg_sdg_number_key'
    ) THEN
        ALTER TABLE sdg ADD CONSTRAINT sdg_sdg_number_key UNIQUE (sdg_number);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS form_of_capital (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE form_of_capital ADD COLUMN IF NOT EXISTS capital_key VARCHAR(100);
ALTER TABLE form_of_capital ADD COLUMN IF NOT EXISTS kokonut_question TEXT;
ALTER TABLE form_of_capital ADD COLUMN IF NOT EXISTS evidence_examples TEXT[] DEFAULT '{}';
ALTER TABLE form_of_capital ADD COLUMN IF NOT EXISTS sort_order INTEGER;
ALTER TABLE form_of_capital ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'form_of_capital_capital_key_key'
    ) THEN
        ALTER TABLE form_of_capital ADD CONSTRAINT form_of_capital_capital_key_key UNIQUE (capital_key);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS pillar_of_value (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pillar_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    core_question TEXT NOT NULL,
    schema_connections TEXT[] DEFAULT '{}',
    sort_order INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS regeneration_principle (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    principle_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    evidence_examples TEXT[] DEFAULT '{}',
    sort_order INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS farm_impact_mapping (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    framework_key VARCHAR(100) NOT NULL,
    dimension_key VARCHAR(100),
    sdg_number INTEGER,
    capital_key VARCHAR(100),
    pillar_key VARCHAR(100),
    claim TEXT NOT NULL,
    evidence_path TEXT,
    evidence_maturity VARCHAR(100) DEFAULT 'planned', -- planned, estimated, measured, verified, published
    reporting_period VARCHAR(100),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_farm_impact_mapping_unique
    ON farm_impact_mapping(location_id, framework_key, COALESCE(dimension_key, ''), COALESCE(sdg_number, 0), COALESCE(capital_key, ''), COALESCE(pillar_key, ''));
CREATE INDEX IF NOT EXISTS idx_farm_impact_mapping_location ON farm_impact_mapping(location_id);
CREATE INDEX IF NOT EXISTS idx_farm_impact_mapping_status ON farm_impact_mapping(status);

-- Colony-powered Kokonut Guild metadata. Colony remains the execution and
-- reputation system; this repo stores pointers, summaries, and governed records.
CREATE TABLE IF NOT EXISTS colony_instance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    colony_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    chain VARCHAR(50) NOT NULL,
    chain_id INTEGER,
    colony_address VARCHAR(42),
    native_token_address VARCHAR(42),
    network_address VARCHAR(42),
    reputation_mining_cycle VARCHAR(66),
    status VARCHAR(50) DEFAULT 'planned', -- planned, active, paused, deprecated
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kokonut_guild (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guild_key VARCHAR(100) NOT NULL UNIQUE,
    colony_instance_id UUID REFERENCES colony_instance(id),
    name VARCHAR(255) NOT NULL,
    purpose TEXT,
    colony_domain_id INTEGER,
    colony_skill_id INTEGER,
    steward_wallet VARCHAR(42),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS guild_contributor (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address VARCHAR(42),
    display_name VARCHAR(255),
    contributor_type VARCHAR(100), -- builder, operator, researcher, steward, partner
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(wallet_address)
);

CREATE TABLE IF NOT EXISTS guild_contribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guild_id UUID NOT NULL REFERENCES kokonut_guild(id) ON DELETE CASCADE,
    contributor_id UUID REFERENCES guild_contributor(id),
    contribution_type VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    contribution_date DATE NOT NULL,
    evidence_cid TEXT,
    evidence_url TEXT,
    points_awarded NUMERIC(18,6) DEFAULT 0,
    colony_task_id VARCHAR(255),
    colony_payment_id VARCHAR(255),
    review_status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guild_contribution_guild ON guild_contribution(guild_id);
CREATE INDEX IF NOT EXISTS idx_guild_contribution_contributor ON guild_contribution(contributor_id);
CREATE INDEX IF NOT EXISTS idx_guild_contribution_review ON guild_contribution(review_status);

CREATE TABLE IF NOT EXISTS guild_reputation_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guild_id UUID NOT NULL REFERENCES kokonut_guild(id) ON DELETE CASCADE,
    contributor_id UUID REFERENCES guild_contributor(id),
    snapshot_date DATE NOT NULL,
    reputation_amount NUMERIC(30,6) NOT NULL DEFAULT 0,
    reputation_pct NUMERIC(8,4),
    source_system VARCHAR(100) DEFAULT 'colony',
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(guild_id, contributor_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS dao_proposal (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_code VARCHAR(100) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    proposal_type VARCHAR(100) NOT NULL, -- farm_funding, guild_bounty, framework_upgrade, partnership, membership, loot_award
    lifecycle_stage VARCHAR(50) DEFAULT 'draft', -- draft, active, grace_period, executed, rejected, cancelled
    venue VARCHAR(100), -- charmverse, daohaus, colony, forum
    location_id UUID REFERENCES location(id),
    guild_id UUID REFERENCES kokonut_guild(id),
    moloch_proposal_id VARCHAR(255),
    colony_motion_id VARCHAR(255),
    requested_amount NUMERIC(18,6),
    requested_token VARCHAR(50),
    public_goods_allocation_pct NUMERIC(6,3),
    success_metrics TEXT,
    evidence_cid TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dao_proposal_stage ON dao_proposal(lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_dao_proposal_location ON dao_proposal(location_id);
CREATE INDEX IF NOT EXISTS idx_dao_proposal_guild ON dao_proposal(guild_id);

-- Farm zones and practice evidence for syntropic/regenerative operations.
CREATE TABLE IF NOT EXISTS farm_zone (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    zone_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    zone_type VARCHAR(100) NOT NULL, -- syntropic_plot, nursery, biofactory, poultry, education, agroforestry, crop_bed
    area_m2 NUMERIC(15,4),
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_farm_zone_location ON farm_zone(location_id);
CREATE INDEX IF NOT EXISTS idx_farm_zone_type ON farm_zone(zone_type);

CREATE TABLE IF NOT EXISTS farm_practice_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id),
    principle_key VARCHAR(100) REFERENCES regeneration_principle(principle_key),
    practice_type VARCHAR(100) NOT NULL,
    event_date DATE NOT NULL,
    description TEXT NOT NULL,
    evidence_cid TEXT,
    evidence_url TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_farm_practice_location ON farm_practice_event(location_id);
CREATE INDEX IF NOT EXISTS idx_farm_practice_principle ON farm_practice_event(principle_key);
CREATE INDEX IF NOT EXISTS idx_farm_practice_status ON farm_practice_event(status);
