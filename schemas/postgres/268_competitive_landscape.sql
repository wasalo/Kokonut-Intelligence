-- ============================================================
-- 268_competitive_landscape.sql
-- Governed external landscape, actors, Five Forces, and signals.
-- ============================================================

CREATE TABLE IF NOT EXISTS competitive_landscape (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('organization', 'location')),
    scope_id UUID NOT NULL,
    industry VARCHAR(160),
    geography VARCHAR(160),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'retired')),
    confidence VARCHAR(20) CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    summary TEXT,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    verified_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (period_end >= period_start),
    CHECK (status NOT IN ('verified', 'published') OR verified_by_party_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS competitive_actor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landscape_id UUID NOT NULL REFERENCES competitive_landscape(id) ON DELETE CASCADE,
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    actor_type VARCHAR(30) NOT NULL CHECK (actor_type IN ('competitor', 'substitute', 'buyer', 'supplier', 'partner', 'new_entrant', 'regulator', 'community')),
    strategic_group VARCHAR(120),
    position_summary TEXT,
    threat_level VARCHAR(20) CHECK (threat_level IN ('low', 'medium', 'high', 'critical')),
    evidence JSONB NOT NULL DEFAULT '[]',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (landscape_id, party_id, actor_type)
);

CREATE TABLE IF NOT EXISTS competitive_force_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landscape_id UUID NOT NULL REFERENCES competitive_landscape(id) ON DELETE CASCADE,
    force_type VARCHAR(30) NOT NULL CHECK (force_type IN ('buyer_power', 'supplier_power', 'competitive_rivalry', 'substitutes', 'new_entrants')),
    pressure_score NUMERIC(5,2) NOT NULL CHECK (pressure_score BETWEEN 0 AND 100),
    trend VARCHAR(20) NOT NULL DEFAULT 'stable' CHECK (trend IN ('improving', 'stable', 'worsening', 'uncertain')),
    rationale TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate' CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS competitive_signal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landscape_id UUID NOT NULL REFERENCES competitive_landscape(id) ON DELETE CASCADE,
    signal_type VARCHAR(40) NOT NULL CHECK (signal_type IN ('market', 'competitor', 'policy', 'climate', 'stakeholder', 'technology', 'supply_chain')),
    source_system VARCHAR(100) NOT NULL,
    source_ref VARCHAR(255),
    content TEXT NOT NULL,
    impact_direction VARCHAR(20) NOT NULL DEFAULT 'uncertain' CHECK (impact_direction IN ('positive', 'negative', 'mixed', 'uncertain')),
    materiality VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (materiality IN ('low', 'medium', 'high', 'critical')),
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate' CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_competitive_landscape_plan ON competitive_landscape(strategy_plan_id, status, period_end DESC);
CREATE INDEX IF NOT EXISTS idx_competitive_landscape_scope ON competitive_landscape(scope_type, scope_id, period_end DESC);
CREATE INDEX IF NOT EXISTS idx_competitive_actor_party ON competitive_actor(party_id, actor_type);
CREATE INDEX IF NOT EXISTS idx_competitive_force_landscape ON competitive_force_observation(landscape_id, force_type, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_competitive_signal_materiality ON competitive_signal(landscape_id, materiality, reviewed_at, observed_at DESC);

DROP TRIGGER IF EXISTS trg_competitive_landscape_updated_at ON competitive_landscape;
CREATE TRIGGER trg_competitive_landscape_updated_at BEFORE UPDATE ON competitive_landscape
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE competitive_landscape IS 'External competitive landscape scoped to an organization/location strategy plan';
COMMENT ON TABLE competitive_actor IS 'Competitive and market actors linked to canonical stakeholder parties';
COMMENT ON TABLE competitive_force_observation IS 'Evidence-backed Porter Five Forces pressure observations';
COMMENT ON TABLE competitive_signal IS 'Continuous external signals that may trigger strategic review';
