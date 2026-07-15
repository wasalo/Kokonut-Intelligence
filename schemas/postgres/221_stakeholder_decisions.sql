-- ============================================================
-- 221_stakeholder_decisions.sql - Stakeholder decision lineage
-- ============================================================

CREATE TABLE IF NOT EXISTS stakeholder_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_key VARCHAR(80) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    decision_type VARCHAR(40) NOT NULL CHECK (decision_type IN ('policy', 'resource_allocation', 'operational', 'technology', 'governance', 'remedy', 'other')),
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    proposed_action TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'rejected', 'in_execution', 'completed', 'cancelled')),
    approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    decision_log_id UUID REFERENCES decision_log(id) ON DELETE SET NULL,
    work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (approval_status <> 'approved' OR approved_by_party_id IS NOT NULL),
    CHECK (status <> 'approved' OR approval_status = 'approved')
);

CREATE INDEX IF NOT EXISTS idx_sdec_status ON stakeholder_decision(status, approval_status);
CREATE INDEX IF NOT EXISTS idx_sdec_scope ON stakeholder_decision(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_sdec_creator ON stakeholder_decision(created_by_party_id);
CREATE INDEX IF NOT EXISTS idx_sdec_work_item ON stakeholder_decision(work_item_id);

CREATE TABLE IF NOT EXISTS stakeholder_decision_participant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES stakeholder_decision(id) ON DELETE CASCADE,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    participation_id UUID REFERENCES stakeholder_participation(id) ON DELETE SET NULL,
    stakeholder_role VARCHAR(30) NOT NULL CHECK (stakeholder_role IN ('affected', 'consulted', 'decision_maker', 'steward', 'observer', 'proxy')),
    participation_status VARCHAR(20) NOT NULL DEFAULT 'invited'
        CHECK (participation_status IN ('invited', 'participated', 'declined', 'absent', 'represented')),
    consent_checked BOOLEAN NOT NULL DEFAULT FALSE,
    perspective_summary TEXT,
    minority_view BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (decision_id, party_id, stakeholder_role),
    CHECK (party_id IS NOT NULL OR participation_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_sdp_decision ON stakeholder_decision_participant(decision_id);
CREATE INDEX IF NOT EXISTS idx_sdp_party ON stakeholder_decision_participant(party_id);

CREATE TABLE IF NOT EXISTS stakeholder_decision_tradeoff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES stakeholder_decision(id) ON DELETE CASCADE,
    interest_id UUID REFERENCES stakeholder_interest(id) ON DELETE SET NULL,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('benefit', 'harm', 'cost', 'risk', 'neutral')),
    description TEXT NOT NULL,
    severity NUMERIC(4,2) CHECK (severity BETWEEN 0 AND 10),
    accepted BOOLEAN NOT NULL DEFAULT FALSE,
    mitigation TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sdt_decision ON stakeholder_decision_tradeoff(decision_id, direction);
CREATE INDEX IF NOT EXISTS idx_sdt_party ON stakeholder_decision_tradeoff(party_id);

CREATE TABLE IF NOT EXISTS stakeholder_decision_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES stakeholder_decision(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    source_id UUID,
    source_key VARCHAR(255),
    evidence_role VARCHAR(30) NOT NULL CHECK (evidence_role IN ('input', 'supporting', 'contradicting', 'impact', 'approval', 'outcome')),
    summary TEXT NOT NULL,
    content_hash VARCHAR(128),
    content_cid TEXT,
    evidence_maturity INTEGER REFERENCES evidence_maturity_level(level),
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    audience VARCHAR(20) NOT NULL DEFAULT 'internal' CHECK (audience IN ('private', 'internal', 'public')),
    added_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sde_decision ON stakeholder_decision_evidence(decision_id, evidence_role);
CREATE INDEX IF NOT EXISTS idx_sde_source ON stakeholder_decision_evidence(source_type, source_id);

CREATE TABLE IF NOT EXISTS stakeholder_decision_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES stakeholder_decision(id) ON DELETE CASCADE,
    outcome_type VARCHAR(30) NOT NULL CHECK (outcome_type IN ('benefit', 'harm', 'metric', 'work_item', 'engagement', 'remedy', 'feedback')),
    source_id UUID,
    summary TEXT NOT NULL,
    outcome_status VARCHAR(20) NOT NULL DEFAULT 'observed'
        CHECK (outcome_status IN ('planned', 'observed', 'verified', 'rejected')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sdo_decision ON stakeholder_decision_outcome(decision_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_sdo_status ON stakeholder_decision_outcome(outcome_status);

CREATE OR REPLACE VIEW v_stakeholder_decision_lineage AS
SELECT
    sd.id AS decision_id,
    sd.decision_key,
    sd.title,
    sd.decision_type,
    sd.scope_type,
    sd.scope_id,
    sd.status,
    sd.approval_status,
    creator.display_name AS created_by_name,
    approver.display_name AS approved_by_name,
    sd.approved_at,
    sd.decision_log_id,
    sd.work_item_id,
    COUNT(DISTINCT sdp.id) AS participant_count,
    COUNT(DISTINCT sdp.id) FILTER (WHERE sdp.participation_status = 'participated') AS participating_count,
    COUNT(DISTINCT sdp.id) FILTER (WHERE sdp.minority_view) AS minority_participant_count,
    COUNT(DISTINCT sdt.id) AS tradeoff_count,
    COUNT(DISTINCT sdt.id) FILTER (WHERE sdt.direction = 'harm' AND NOT sdt.accepted) AS unresolved_harm_count,
    COUNT(DISTINCT sde.id) AS evidence_count,
    COUNT(DISTINCT sde.id) FILTER (WHERE sde.verified) AS verified_evidence_count,
    COUNT(DISTINCT sdo.id) AS outcome_count,
    MAX(sdo.observed_at) AS last_outcome_at
FROM stakeholder_decision sd
LEFT JOIN party creator ON creator.id = sd.created_by_party_id
LEFT JOIN party approver ON approver.id = sd.approved_by_party_id
LEFT JOIN stakeholder_decision_participant sdp ON sdp.decision_id = sd.id
LEFT JOIN stakeholder_decision_tradeoff sdt ON sdt.decision_id = sd.id
LEFT JOIN stakeholder_decision_evidence sde ON sde.decision_id = sd.id
LEFT JOIN stakeholder_decision_outcome sdo ON sdo.decision_id = sd.id
GROUP BY sd.id, sd.decision_key, sd.title, sd.decision_type, sd.scope_type, sd.scope_id,
         sd.status, sd.approval_status, creator.display_name, approver.display_name,
         sd.approved_at, sd.decision_log_id, sd.work_item_id;

COMMENT ON TABLE stakeholder_decision IS 'Stakeholder-scoped decision with explicit approval, trade-offs, evidence, and outcomes';
COMMENT ON TABLE stakeholder_decision_tradeoff IS 'Explicit stakeholder benefits, harms, costs, risks, and mitigations';
COMMENT ON TABLE stakeholder_decision_evidence IS 'Evidence lineage for stakeholder decisions';
COMMENT ON VIEW v_stakeholder_decision_lineage IS 'Internal decision lineage summary; public exposure requires deliberate projection';
