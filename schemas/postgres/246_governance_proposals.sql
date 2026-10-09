-- ============================================================
-- 246_governance_proposals.sql
-- Structural governance changes and integrative objections.
-- ============================================================

CREATE TABLE IF NOT EXISTS governance_proposal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_key VARCHAR(120) NOT NULL UNIQUE,
    circle_id UUID NOT NULL REFERENCES governance_circle(id) ON DELETE RESTRICT,
    proposal_type VARCHAR(40) NOT NULL CHECK (proposal_type IN (
        'create_role', 'amend_role', 'retire_role', 'change_domain',
        'change_policy', 'create_circle', 'change_circle_scope',
        'retire_circle', 'appoint_representative', 'change_decision_rule'
    )),
    title VARCHAR(255) NOT NULL,
    purpose TEXT NOT NULL,
    current_state TEXT,
    proposed_state TEXT NOT NULL,
    tension_id UUID REFERENCES governance_tension(id) ON DELETE SET NULL,
    proposed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    proposed_by_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    affected_scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (affected_scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    affected_scope_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'in_review', 'approved', 'rejected', 'implemented', 'superseded', 'cancelled')),
    harm_review_status VARCHAR(20) NOT NULL DEFAULT 'not_required'
        CHECK (harm_review_status IN ('not_required', 'required', 'clear', 'blocked')),
    minority_review_status VARCHAR(20) NOT NULL DEFAULT 'not_required'
        CHECK (minority_review_status IN ('not_required', 'required', 'reviewed', 'blocked')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    implementation_work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    review_due_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    implementation_summary TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status NOT IN ('submitted', 'in_review', 'approved', 'implemented') OR proposed_by_party_id IS NOT NULL),
    CHECK (status NOT IN ('approved', 'implemented') OR approved_by_party_id IS NOT NULL),
    CHECK (status <> 'implemented' OR implementation_work_item_id IS NOT NULL),
    CHECK (status <> 'implemented' OR NULLIF(BTRIM(implementation_summary), '') IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_governance_proposal_circle
    ON governance_proposal(circle_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_proposal_tension
    ON governance_proposal(tension_id);
CREATE INDEX IF NOT EXISTS idx_governance_proposal_review
    ON governance_proposal(review_due_at)
    WHERE status IN ('submitted', 'in_review', 'approved');

CREATE TABLE IF NOT EXISTS governance_proposal_objection (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES governance_proposal(id) ON DELETE CASCADE,
    objector_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    objector_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    objection_type VARCHAR(40) NOT NULL CHECK (objection_type IN (
        'material_harm', 'scope_conflict', 'authority_conflict',
        'consent_failure', 'evidence_failure', 'representation_gap',
        'operational_risk', 'legal_or_policy_conflict', 'minority_view'
    )),
    objection_text TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    severity SMALLINT NOT NULL DEFAULT 3 CHECK (severity BETWEEN 1 AND 5),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'accepted', 'rejected', 'resolved', 'withdrawn')),
    response TEXT,
    resolved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (objector_party_id IS NOT NULL OR objector_role_id IS NOT NULL),
    CHECK (status NOT IN ('accepted', 'rejected', 'resolved') OR NULLIF(BTRIM(response), '') IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_governance_objection_proposal
    ON governance_proposal_objection(proposal_id, status, objection_type);

CREATE TABLE IF NOT EXISTS governance_proposal_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES governance_proposal(id) ON DELETE CASCADE,
    reviewer_party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    review_type VARCHAR(30) NOT NULL CHECK (review_type IN ('harm', 'minority', 'scope', 'evidence', 'implementation')),
    result VARCHAR(20) NOT NULL CHECK (result IN ('required', 'clear', 'blocked', 'reviewed', 'needs_revision')),
    notes TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_governance_proposal_review_proposal
    ON governance_proposal_review(proposal_id, review_type, created_at DESC);

CREATE OR REPLACE FUNCTION enforce_governance_proposal_approval()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('approved', 'implemented') THEN
        IF NEW.approved_by_party_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM party WHERE id = NEW.approved_by_party_id AND party_type = 'person'
        ) THEN
            RAISE EXCEPTION 'governance proposals require an identified human approver';
        END IF;
        IF NEW.harm_review_status IN ('required', 'blocked') THEN
            RAISE EXCEPTION 'governance proposal has unresolved material harm review';
        END IF;
        IF NEW.minority_review_status IN ('required', 'blocked') THEN
            RAISE EXCEPTION 'governance proposal has unresolved minority review';
        END IF;
        IF EXISTS (
            SELECT 1 FROM governance_proposal_objection o
            WHERE o.proposal_id = NEW.id AND o.status = 'open'
              AND o.objection_type IN ('material_harm', 'consent_failure')
        ) THEN
            RAISE EXCEPTION 'governance proposal has an unresolved material objection';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_proposal_approval ON governance_proposal;
CREATE TRIGGER trg_governance_proposal_approval
    BEFORE INSERT OR UPDATE ON governance_proposal
    FOR EACH ROW EXECUTE FUNCTION enforce_governance_proposal_approval();

DROP TRIGGER IF EXISTS trg_governance_proposal_updated_at ON governance_proposal;
CREATE TRIGGER trg_governance_proposal_updated_at
    BEFORE UPDATE ON governance_proposal
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_governance_proposal_objection_updated_at ON governance_proposal_objection;
CREATE TRIGGER trg_governance_proposal_objection_updated_at
    BEFORE UPDATE ON governance_proposal_objection
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE VIEW v_governance_proposal_lineage AS
SELECT
    p.id AS proposal_id,
    p.proposal_key,
    p.circle_id,
    c.circle_key,
    p.proposal_type,
    p.title,
    p.status,
    p.tension_id,
    p.proposed_by_party_id,
    proposer.display_name AS proposer_name,
    p.proposed_by_role_id,
    role.role_key AS proposer_role_key,
    p.harm_review_status,
    p.minority_review_status,
    p.approved_by_party_id,
    approver.display_name AS approver_name,
    p.approved_at,
    p.implementation_work_item_id,
    p.review_due_at,
    COUNT(o.id) AS objection_count,
    COUNT(o.id) FILTER (WHERE o.status = 'open') AS open_objection_count,
    COUNT(o.id) FILTER (WHERE o.status = 'open' AND o.objection_type IN ('material_harm', 'consent_failure')) AS open_material_objection_count,
    COUNT(r.id) AS review_count
FROM governance_proposal p
JOIN governance_circle c ON c.id = p.circle_id
LEFT JOIN party proposer ON proposer.id = p.proposed_by_party_id
LEFT JOIN governance_role role ON role.id = p.proposed_by_role_id
LEFT JOIN party approver ON approver.id = p.approved_by_party_id
LEFT JOIN governance_proposal_objection o ON o.proposal_id = p.id
LEFT JOIN governance_proposal_review r ON r.proposal_id = p.id
GROUP BY p.id, p.proposal_key, p.circle_id, c.circle_key, p.proposal_type,
         p.title, p.status, p.tension_id, p.proposed_by_party_id,
         proposer.display_name, p.proposed_by_role_id, role.role_key,
         p.harm_review_status, p.minority_review_status, p.approved_by_party_id,
         approver.display_name, p.approved_at, p.implementation_work_item_id,
         p.review_due_at;

COMMENT ON TABLE governance_proposal IS 'Governed change to a role, circle, domain, policy, or decision rule';
COMMENT ON TABLE governance_proposal_objection IS 'Role-relevant objection and response record for integrative governance review';
COMMENT ON TABLE governance_proposal_review IS 'Human review evidence for harm, minority, scope, evidence, and implementation gates';
COMMENT ON VIEW v_governance_proposal_lineage IS 'Internal proposal lineage with objection and review health';
