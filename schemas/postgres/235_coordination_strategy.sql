-- ============================================================
-- 235_coordination_strategy.sql - Governed coordination records
-- ============================================================
-- Models non-equity alliances and knowledge networks. It records
-- commitments and outcomes without implying legal ownership or
-- authorizing financial or operational execution.

CREATE TABLE IF NOT EXISTS coordination_alliance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    coordination_type VARCHAR(30) NOT NULL CHECK (coordination_type IN ('alliance', 'cooperative_network', 'knowledge_network')),
    purpose TEXT NOT NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'location', 'organization', 'value_stream', 'initiative')),
    scope_id UUID,
    strategy_map_id UUID REFERENCES strategy_map(id) ON DELETE SET NULL,
    value_stream_id UUID REFERENCES value_stream_definition(id) ON DELETE SET NULL,
    steward_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'proposed', 'approved', 'active', 'paused', 'completed', 'dissolved', 'rejected')),
    approval_basis TEXT,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at),
    CHECK (status NOT IN ('approved', 'active', 'completed') OR approved_by_party_id IS NOT NULL),
    CHECK (status NOT IN ('approved', 'active', 'completed') OR approved_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS coordination_participant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    role VARCHAR(30) NOT NULL CHECK (role IN ('initiator', 'participant', 'steward', 'observer', 'knowledge_holder', 'affected_party')),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'invited', 'accepted', 'active', 'paused', 'exited', 'rejected')),
    contribution_expectation TEXT,
    benefit_expectation TEXT,
    consent_event_id UUID REFERENCES stakeholder_consent(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (alliance_id, party_id),
    CHECK (status <> 'active' OR consent_event_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS coordination_objective (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    objective_type VARCHAR(30) NOT NULL CHECK (objective_type IN ('shared_value', 'capability', 'knowledge', 'market_access', 'stewardship', 'resilience', 'other')),
    target_value NUMERIC,
    target_unit VARCHAR(50),
    harm_if_missed TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'achieved', 'not_achieved', 'retired')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coordination_contribution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    participant_id UUID NOT NULL REFERENCES coordination_participant(id) ON DELETE CASCADE,
    contribution_type VARCHAR(30) NOT NULL CHECK (contribution_type IN ('capital', 'capability', 'resource', 'data', 'knowledge', 'market_access', 'labor', 'stewardship', 'other')),
    description TEXT NOT NULL,
    committed_value NUMERIC,
    value_unit VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'committed', 'delivered', 'withdrawn', 'disputed')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    verified_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coordination_benefit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    participant_id UUID REFERENCES coordination_participant(id) ON DELETE SET NULL,
    benefit_type VARCHAR(30) NOT NULL CHECK (benefit_type IN ('income', 'access', 'capability', 'knowledge', 'market_access', 'ecological', 'governance', 'other')),
    description TEXT NOT NULL,
    expected_value NUMERIC,
    realized_value NUMERIC,
    value_unit VARCHAR(50),
    allocation_status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (allocation_status IN ('proposed', 'approved', 'delivered', 'disputed', 'rejected')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (allocation_status <> 'approved' OR approved_by_party_id IS NOT NULL),
    CHECK (allocation_status <> 'approved' OR approved_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS coordination_risk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    risk_type VARCHAR(30) NOT NULL CHECK (risk_type IN ('capture', 'exclusion', 'dependency', 'privacy', 'ecological', 'financial', 'operational', 'reputational', 'other')),
    description TEXT NOT NULL,
    likelihood NUMERIC(5,4) CHECK (likelihood BETWEEN 0 AND 1),
    impact NUMERIC(5,4) CHECK (impact BETWEEN 0 AND 1),
    mitigation TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'monitoring', 'mitigated', 'accepted', 'closed')),
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coordination_knowledge_exchange (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    from_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    to_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    topic VARCHAR(255) NOT NULL,
    exchange_type VARCHAR(30) NOT NULL CHECK (exchange_type IN ('practice', 'data', 'training', 'research', 'market_signal', 'artifact', 'other')),
    artifact_uri TEXT,
    consent_scope VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'scheduled', 'completed', 'restricted', 'rejected')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    occurred_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (to_party_id IS NULL OR from_party_id <> to_party_id)
);

CREATE TABLE IF NOT EXISTS coordination_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    reviewer_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    participation_summary TEXT NOT NULL,
    benefit_summary TEXT NOT NULL,
    harm_and_risk_summary TEXT NOT NULL,
    findings TEXT NOT NULL,
    recommendation VARCHAR(30) NOT NULL CHECK (recommendation IN ('continue', 'amend', 'pause', 'close', 'escalate')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'approved', 'rejected')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (period_end >= period_start),
    CHECK (status <> 'approved' OR approved_by_party_id IS NOT NULL),
    CHECK (status <> 'approved' OR approved_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_coord_alliance_status ON coordination_alliance(status, coordination_type);
CREATE INDEX IF NOT EXISTS idx_coord_participant_party ON coordination_participant(party_id, status);
CREATE INDEX IF NOT EXISTS idx_coord_objective_alliance ON coordination_objective(alliance_id, status);
CREATE INDEX IF NOT EXISTS idx_coord_contribution_alliance ON coordination_contribution(alliance_id, status);
CREATE INDEX IF NOT EXISTS idx_coord_benefit_alliance ON coordination_benefit(alliance_id, allocation_status);
CREATE INDEX IF NOT EXISTS idx_coord_risk_alliance ON coordination_risk(alliance_id, status);
CREATE INDEX IF NOT EXISTS idx_coord_exchange_alliance ON coordination_knowledge_exchange(alliance_id, status);
CREATE INDEX IF NOT EXISTS idx_coord_review_alliance ON coordination_review(alliance_id, period_end DESC);

DROP TRIGGER IF EXISTS trg_coordination_alliance_updated_at ON coordination_alliance;
CREATE TRIGGER trg_coordination_alliance_updated_at
    BEFORE UPDATE ON coordination_alliance
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION enforce_coordination_lifecycle()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    alliance_status VARCHAR(20);
BEGIN
    IF TG_TABLE_NAME = 'coordination_participant' AND NEW.status = 'active' THEN
        SELECT status INTO alliance_status FROM coordination_alliance WHERE id = NEW.alliance_id;
        IF alliance_status NOT IN ('approved', 'active') THEN
            RAISE EXCEPTION 'coordination participants require an approved or active alliance';
        END IF;
    ELSIF TG_TABLE_NAME = 'coordination_knowledge_exchange' AND NEW.status = 'completed' THEN
        SELECT status INTO alliance_status FROM coordination_alliance WHERE id = NEW.alliance_id;
        IF alliance_status <> 'active' THEN
            RAISE EXCEPTION 'knowledge exchange requires an active alliance';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_coordination_participant_lifecycle ON coordination_participant;
CREATE TRIGGER trg_coordination_participant_lifecycle
    BEFORE INSERT OR UPDATE ON coordination_participant
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_lifecycle();

DROP TRIGGER IF EXISTS trg_coordination_exchange_lifecycle ON coordination_knowledge_exchange;
CREATE TRIGGER trg_coordination_exchange_lifecycle
    BEFORE INSERT OR UPDATE ON coordination_knowledge_exchange
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_lifecycle();

CREATE OR REPLACE VIEW v_coordination_health AS
SELECT ca.id AS alliance_id,
       ca.name,
       ca.coordination_type,
       ca.status,
       COUNT(DISTINCT cp.id) FILTER (WHERE cp.status = 'active') AS active_participant_count,
       COUNT(DISTINCT co.id) FILTER (WHERE co.status = 'active') AS active_objective_count,
       COUNT(DISTINCT cc.id) FILTER (WHERE cc.status IN ('committed', 'delivered')) AS contribution_count,
       COUNT(DISTINCT cb.id) FILTER (WHERE cb.allocation_status IN ('approved', 'delivered')) AS benefit_count,
       COUNT(DISTINCT cr.id) FILTER (WHERE cr.status IN ('open', 'monitoring')) AS open_risk_count,
       COUNT(DISTINCT ke.id) FILTER (WHERE ke.status = 'completed') AS completed_exchange_count,
       MAX(rv.period_end) AS latest_review_end
FROM coordination_alliance ca
LEFT JOIN coordination_participant cp ON cp.alliance_id = ca.id
LEFT JOIN coordination_objective co ON co.alliance_id = ca.id
LEFT JOIN coordination_contribution cc ON cc.alliance_id = ca.id
LEFT JOIN coordination_benefit cb ON cb.alliance_id = ca.id
LEFT JOIN coordination_risk cr ON cr.alliance_id = ca.id
LEFT JOIN coordination_knowledge_exchange ke ON ke.alliance_id = ca.id
LEFT JOIN coordination_review rv ON rv.alliance_id = ca.id
GROUP BY ca.id, ca.name, ca.coordination_type, ca.status;

COMMENT ON TABLE coordination_alliance IS 'Governed non-equity alliance or knowledge network; approval does not authorize legal, financial, or operational execution';
COMMENT ON VIEW v_coordination_health IS 'Internal coordination health rollup with participation, contribution, benefit, risk, and knowledge exchange counts';
