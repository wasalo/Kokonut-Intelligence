-- ============================================================
-- 227_stakeholder_identity_accountability.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS party_resolution_case (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(100) NOT NULL,
    source_type VARCHAR(80) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    candidate_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    proposed_party_type VARCHAR(30) NOT NULL,
    match_method VARCHAR(40) NOT NULL CHECK (match_method IN ('manual', 'exact_identifier', 'verified_document', 'community_review', 'imported')),
    confidence NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'in_review', 'approved', 'rejected', 'superseded')),
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_system, source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_party_resolution_status ON party_resolution_case(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_party_resolution_party ON party_resolution_case(candidate_party_id);

CREATE TABLE IF NOT EXISTS party_merge_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    canonical_party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    merged_by_party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    merged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (source_party_id <> canonical_party_id)
);

CREATE INDEX IF NOT EXISTS idx_party_merge_source ON party_merge_event(source_party_id);
CREATE INDEX IF NOT EXISTS idx_party_merge_canonical ON party_merge_event(canonical_party_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_party_identifier_verified_source
    ON party_identifier(source_system, identifier_type, source_id)
    WHERE verification_status = 'verified' AND source_id IS NOT NULL;

ALTER TABLE party_relationship ADD COLUMN IF NOT EXISTS accountable_party_id UUID REFERENCES party(id) ON DELETE SET NULL;
ALTER TABLE party_relationship ADD COLUMN IF NOT EXISTS responsibility_id UUID REFERENCES responsibility_assignment(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_party_relationship_accountable ON party_relationship(accountable_party_id, status);

CREATE OR REPLACE VIEW v_canonical_party_source_links AS
SELECT pi.source_system, pi.source_id, pi.identifier_type, pi.identifier_value,
       pi.party_id, p.party_type, p.display_name, pi.verification_status,
       pi.confidence, pi.reviewed_by, pi.reviewed_at
FROM party_identifier pi
JOIN party p ON p.id = pi.party_id
WHERE pi.verification_status = 'verified';

CREATE OR REPLACE VIEW v_party_resolution_queue AS
SELECT prc.id AS resolution_case_id, prc.source_system, prc.source_type, prc.source_id,
       prc.candidate_party_id, p.display_name AS candidate_name,
       prc.proposed_party_type, prc.match_method, prc.confidence, prc.status,
       prc.created_at, prc.reviewed_at
FROM party_resolution_case prc
LEFT JOIN party p ON p.id = prc.candidate_party_id
WHERE prc.status IN ('proposed', 'in_review');

COMMENT ON VIEW v_canonical_party_source_links IS 'Only human-reviewed verified source records resolve to canonical parties';
COMMENT ON VIEW v_party_resolution_queue IS 'Identity candidates awaiting human review';
