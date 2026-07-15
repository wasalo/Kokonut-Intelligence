-- ============================================================
-- 222_cooperative_trust.sql - Cooperative governance and trust evidence
-- ============================================================

ALTER TABLE cooperative_membership ADD COLUMN IF NOT EXISTS party_id UUID REFERENCES party(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_coop_mem_party ON cooperative_membership(party_id);
ALTER TABLE buyer_profile ADD COLUMN IF NOT EXISTS party_id UUID REFERENCES party(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_buyer_party ON buyer_profile(party_id);

CREATE TABLE IF NOT EXISTS cooperative_meeting (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    meeting_type VARCHAR(30) NOT NULL CHECK (meeting_type IN ('general', 'board', 'committee', 'emergency', 'annual', 'other')),
    scheduled_at TIMESTAMPTZ NOT NULL,
    held_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'held', 'cancelled', 'adjourned')),
    quorum_required NUMERIC(6,3),
    quorum_met BOOLEAN,
    agenda TEXT,
    minutes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cooperative_proposal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    meeting_id UUID REFERENCES cooperative_meeting(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    proposed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'in_review', 'approved', 'rejected', 'withdrawn')),
    submitted_at TIMESTAMPTZ,
    decided_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cooperative_motion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES cooperative_proposal(id) ON DELETE CASCADE,
    motion_type VARCHAR(30) NOT NULL CHECK (motion_type IN ('approve', 'amend', 'defer', 'reject', 'refer', 'other')),
    text TEXT NOT NULL,
    moved_by_membership_id UUID REFERENCES cooperative_membership(id) ON DELETE SET NULL,
    seconded_by_membership_id UUID REFERENCES cooperative_membership(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'passed', 'failed', 'withdrawn')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cooperative_vote (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    motion_id UUID NOT NULL REFERENCES cooperative_motion(id) ON DELETE CASCADE,
    membership_id UUID NOT NULL REFERENCES cooperative_membership(id) ON DELETE CASCADE,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    vote VARCHAR(20) NOT NULL CHECK (vote IN ('for', 'against', 'abstain', 'recuse')),
    cast_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (motion_id, membership_id)
);

CREATE TABLE IF NOT EXISTS cooperative_quorum (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID NOT NULL REFERENCES cooperative_meeting(id) ON DELETE CASCADE,
    eligible_count INTEGER NOT NULL CHECK (eligible_count >= 0),
    present_count INTEGER NOT NULL CHECK (present_count >= 0),
    required_pct NUMERIC(6,3) NOT NULL CHECK (required_pct BETWEEN 0 AND 100),
    achieved BOOLEAN NOT NULL,
    verified_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    verified_at TIMESTAMPTZ,
    UNIQUE (meeting_id)
);

CREATE TABLE IF NOT EXISTS cooperative_delegation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    delegator_membership_id UUID NOT NULL REFERENCES cooperative_membership(id) ON DELETE CASCADE,
    delegate_membership_id UUID NOT NULL REFERENCES cooperative_membership(id) ON DELETE CASCADE,
    scope_type VARCHAR(20) NOT NULL DEFAULT 'meeting' CHECK (scope_type IN ('meeting', 'proposal', 'motion', 'general')),
    scope_id UUID,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ends_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'expired')),
    reason TEXT,
    CHECK (delegator_membership_id <> delegate_membership_id),
    CHECK (ends_at IS NULL OR ends_at >= starts_at)
);

CREATE TABLE IF NOT EXISTS cooperative_conflict_declaration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    membership_id UUID REFERENCES cooperative_membership(id) ON DELETE SET NULL,
    scope_type VARCHAR(20) NOT NULL DEFAULT 'cooperative' CHECK (scope_type IN ('cooperative', 'meeting', 'proposal', 'motion', 'distribution')),
    scope_id UUID,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'declared' CHECK (status IN ('declared', 'reviewed', 'managed', 'dismissed')),
    mitigation TEXT,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (party_id IS NOT NULL OR membership_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS cooperative_distribution_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    proposal_id UUID REFERENCES cooperative_proposal(id) ON DELETE SET NULL,
    stakeholder_decision_id UUID REFERENCES stakeholder_decision(id) ON DELETE SET NULL,
    distribution_type VARCHAR(30) NOT NULL CHECK (distribution_type IN ('surplus', 'dividend', 'benefit', 'remedy', 'reserve', 'cost_share')),
    amount NUMERIC(15,2) NOT NULL CHECK (amount >= 0),
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    rationale TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'approved', 'executed', 'rejected')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'approved' OR approved_by_party_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS buyer_verification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id UUID NOT NULL REFERENCES buyer_profile(id) ON DELETE CASCADE,
    verification_type VARCHAR(30) NOT NULL CHECK (verification_type IN ('identity', 'registration', 'tax', 'capacity', 'payment_history', 'cold_chain', 'reference', 'other')),
    method VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'rejected', 'expired', 'appealed')),
    evidence_hash VARCHAR(128),
    evidence_cid TEXT,
    source_type VARCHAR(50),
    source_id UUID,
    verified_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    verified_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    rejection_reason TEXT,
    correction_requested BOOLEAN NOT NULL DEFAULT FALSE,
    appeal_status VARCHAR(20) NOT NULL DEFAULT 'none' CHECK (appeal_status IN ('none', 'open', 'resolved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_buyer_verification_buyer ON buyer_verification(buyer_id, status);

CREATE TABLE IF NOT EXISTS market_dispute (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES market_order(id) ON DELETE RESTRICT,
    opened_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    dispute_type VARCHAR(30) NOT NULL CHECK (dispute_type IN ('quality', 'quantity', 'payment', 'delivery', 'damage', 'contract', 'other')),
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'rejected', 'appealed', 'closed')),
    summary TEXT NOT NULL,
    requested_remedy TEXT,
    resolution TEXT,
    resolved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    correction_requested BOOLEAN NOT NULL DEFAULT FALSE,
    appeal_status VARCHAR(20) NOT NULL DEFAULT 'none' CHECK (appeal_status IN ('none', 'open', 'resolved'))
);

CREATE TABLE IF NOT EXISTS market_dispute_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispute_id UUID NOT NULL REFERENCES market_dispute(id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN ('opened', 'evidence_added', 'response', 'mediation', 'resolution', 'appeal', 'correction')),
    actor_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    summary TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS party_trust_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    relationship_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    dimension VARCHAR(40) NOT NULL CHECK (dimension IN ('identity', 'delivery', 'quality', 'payment', 'governance', 'participation', 'ecological_stewardship', 'dispute_resolution', 'credential', 'attestation', 'other')),
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('supporting', 'contradicting', 'neutral')),
    source_type VARCHAR(60) NOT NULL,
    source_id UUID,
    source_label TEXT,
    summary TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    confidence NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
    uncertainty NUMERIC(5,4) CHECK (uncertainty BETWEEN 0 AND 1),
    evidence_hash VARCHAR(128),
    evidence_cid TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'corrected', 'superseded', 'rejected')),
    correction_status VARCHAR(20) NOT NULL DEFAULT 'none' CHECK (correction_status IN ('none', 'requested', 'accepted', 'rejected')),
    appeal_status VARCHAR(20) NOT NULL DEFAULT 'none' CHECK (appeal_status IN ('none', 'open', 'resolved')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trust_evidence_subject ON party_trust_evidence(subject_party_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_trust_evidence_dimension ON party_trust_evidence(dimension, direction);

CREATE TABLE IF NOT EXISTS party_trust_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    relationship_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    as_of TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    formula_version VARCHAR(40) NOT NULL,
    dimensions JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    uncertainty NUMERIC(5,4) CHECK (uncertainty BETWEEN 0 AND 1),
    limitations TEXT NOT NULL,
    generated_by VARCHAR(100) NOT NULL DEFAULT 'system',
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS relationship_risk_indicator (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    relationship_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    risk_key VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    rationale TEXT NOT NULL,
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    uncertainty NUMERIC(5,4) CHECK (uncertainty BETWEEN 0 AND 1),
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'monitoring', 'mitigated', 'dismissed')),
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW v_cooperative_governance_health AS
SELECT c.id AS cooperative_id, c.name,
       COUNT(DISTINCT cm.id) FILTER (WHERE cm.status = 'active') AS active_member_count,
       COUNT(DISTINCT mt.id) AS meeting_count,
       COUNT(DISTINCT cp.id) FILTER (WHERE cp.status IN ('submitted', 'in_review')) AS open_proposal_count,
       COUNT(DISTINCT cd.id) FILTER (WHERE cd.status IN ('declared', 'reviewed')) AS open_conflict_count,
       COUNT(DISTINCT cdd.id) FILTER (WHERE cdd.status = 'proposed') AS pending_distribution_count
FROM cooperative c
LEFT JOIN cooperative_membership cm ON cm.cooperative_id = c.id
LEFT JOIN cooperative_meeting mt ON mt.cooperative_id = c.id
LEFT JOIN cooperative_proposal cp ON cp.cooperative_id = c.id
LEFT JOIN cooperative_conflict_declaration cd ON cd.cooperative_id = c.id
LEFT JOIN cooperative_distribution_decision cdd ON cdd.cooperative_id = c.id
GROUP BY c.id, c.name;

CREATE OR REPLACE VIEW v_party_trust_profile AS
SELECT p.id AS party_id, p.display_name, p.party_type,
       COUNT(DISTINCT e.id) FILTER (WHERE e.status = 'active') AS evidence_count,
       COUNT(DISTINCT e.id) FILTER (WHERE e.status = 'active' AND e.direction = 'supporting') AS supporting_evidence_count,
       COUNT(DISTINCT e.id) FILTER (WHERE e.status = 'active' AND e.direction = 'contradicting') AS contradicting_evidence_count,
       COUNT(DISTINCT e.id) FILTER (WHERE e.correction_status = 'requested' OR e.appeal_status = 'open') AS contested_evidence_count,
       COUNT(DISTINCT r.id) FILTER (WHERE r.status IN ('open', 'monitoring')) AS open_risk_count,
       MAX(e.observed_at) AS latest_evidence_at,
       MIN(e.observed_at) AS earliest_evidence_at,
       MAX(s.as_of) AS latest_snapshot_at,
       MAX(s.uncertainty) FILTER (WHERE s.as_of = (SELECT MAX(s2.as_of) FROM party_trust_snapshot s2 WHERE s2.subject_party_id = p.id)) AS latest_uncertainty,
       'No universal reputation score; inspect dimensions, sources, age, uncertainty, corrections, and appeals.' AS interpretation
FROM party p
LEFT JOIN party_trust_evidence e ON e.subject_party_id = p.id
LEFT JOIN relationship_risk_indicator r ON r.subject_party_id = p.id
LEFT JOIN party_trust_snapshot s ON s.subject_party_id = p.id
GROUP BY p.id, p.display_name, p.party_type;

CREATE OR REPLACE VIEW v_party_trust_evidence_timeline AS
SELECT e.id, e.subject_party_id, subject.display_name AS subject_name,
       e.relationship_party_id, relationship.display_name AS relationship_name,
       e.dimension, e.direction, e.source_type, e.source_id, e.source_label,
       e.summary, e.observed_at, e.expires_at, e.confidence, e.uncertainty,
       e.status, e.correction_status, e.appeal_status
FROM party_trust_evidence e
JOIN party subject ON subject.id = e.subject_party_id
LEFT JOIN party relationship ON relationship.id = e.relationship_party_id;

CREATE OR REPLACE VIEW v_market_dispute_performance AS
SELECT COUNT(*) AS dispute_count,
       COUNT(*) FILTER (WHERE status IN ('resolved', 'closed')) AS resolved_count,
       COUNT(*) FILTER (WHERE status IN ('open', 'investigating', 'appealed')) AS open_count,
       AVG(EXTRACT(EPOCH FROM (COALESCE(resolved_at, NOW()) - opened_at)) / 86400.0) AS average_resolution_days,
       COUNT(*) FILTER (WHERE appeal_status = 'open') AS open_appeal_count,
       COUNT(*) FILTER (WHERE correction_requested) AS correction_request_count
FROM market_dispute;

COMMENT ON VIEW v_party_trust_profile IS 'Explainable trust profile; deliberately excludes a universal reputation score';
COMMENT ON VIEW v_party_trust_evidence_timeline IS 'Evidence timeline with source, age, confidence, uncertainty, correction, and appeal state';
