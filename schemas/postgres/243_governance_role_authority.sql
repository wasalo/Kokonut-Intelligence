-- ============================================================
-- 243_governance_role_authority.sql
-- Role assignments, authority domains, and policies.
-- ============================================================

CREATE TABLE IF NOT EXISTS governance_role_domain (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES governance_role(id) ON DELETE CASCADE,
    domain_type VARCHAR(40) NOT NULL,
    domain_key VARCHAR(160) NOT NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    authority_level VARCHAR(20) NOT NULL DEFAULT 'recommend'
        CHECK (authority_level IN ('observe', 'recommend', 'decide', 'execute')),
    constraints JSONB NOT NULL DEFAULT '{}'::jsonb,
    requires_human_approval BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (role_id, domain_type, domain_key, scope_type, scope_id)
);

CREATE INDEX IF NOT EXISTS idx_governance_role_domain_lookup
    ON governance_role_domain(domain_type, domain_key, scope_type, scope_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_role_domain_role
    ON governance_role_domain(role_id, status);

CREATE TABLE IF NOT EXISTS governance_role_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES governance_role(id) ON DELETE CASCADE,
    policy_key VARCHAR(120) NOT NULL,
    policy_text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'active', 'retired', 'rejected')),
    effective_from TIMESTAMPTZ,
    effective_until TIMESTAMPTZ,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (role_id, policy_key),
    CHECK (effective_until IS NULL OR effective_from IS NULL OR effective_until >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_governance_role_policy_role
    ON governance_role_policy(role_id, status);

CREATE TABLE IF NOT EXISTS governance_role_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES governance_role(id) ON DELETE RESTRICT,
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    assignment_type VARCHAR(20) NOT NULL DEFAULT 'primary'
        CHECK (assignment_type IN ('primary', 'delegate', 'representative', 'interim')),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'active', 'suspended', 'ended', 'rejected')),
    assigned_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    mandate TEXT,
    recusal_status VARCHAR(20) NOT NULL DEFAULT 'clear'
        CHECK (recusal_status IN ('clear', 'declared', 'recused')),
    effective_from TIMESTAMPTZ,
    effective_until TIMESTAMPTZ,
    review_due_at TIMESTAMPTZ,
    approval_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'active' OR effective_from IS NOT NULL),
    CHECK (effective_until IS NULL OR effective_from IS NULL OR effective_until >= effective_from),
    CHECK (assignment_type <> 'delegate' OR NULLIF(BTRIM(mandate), '') IS NOT NULL),
    CHECK (status <> 'active' OR approved_by_party_id IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_governance_primary_role_assignment
    ON governance_role_assignment(role_id)
    WHERE assignment_type = 'primary' AND status = 'active';
CREATE INDEX IF NOT EXISTS idx_governance_role_assignment_party
    ON governance_role_assignment(party_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_role_assignment_role
    ON governance_role_assignment(role_id, status, effective_until);
CREATE INDEX IF NOT EXISTS idx_governance_role_assignment_review
    ON governance_role_assignment(review_due_at)
    WHERE status = 'active';

ALTER TABLE responsibility_assignment
    ADD COLUMN IF NOT EXISTS governance_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_responsibility_governance_role
    ON responsibility_assignment(governance_role_id);

CREATE OR REPLACE FUNCTION enforce_governance_role_assignment()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'active' THEN
        IF NOT EXISTS (
            SELECT 1 FROM governance_role r
            JOIN governance_circle c ON c.id = r.circle_id
            WHERE r.id = NEW.role_id AND r.status = 'active' AND c.status = 'active'
        ) THEN
            RAISE EXCEPTION 'active role assignment requires an active role and circle';
        END IF;
        IF NEW.approved_by_party_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM party WHERE id = NEW.approved_by_party_id AND party_type = 'person'
        ) THEN
            RAISE EXCEPTION 'active role assignment requires an identified human approver';
        END IF;
        IF NEW.recusal_status = 'recused' THEN
            RAISE EXCEPTION 'recused party cannot hold an active role assignment';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_role_assignment ON governance_role_assignment;
CREATE TRIGGER trg_governance_role_assignment
    BEFORE INSERT OR UPDATE ON governance_role_assignment
    FOR EACH ROW EXECUTE FUNCTION enforce_governance_role_assignment();

DROP TRIGGER IF EXISTS trg_governance_role_domain_updated_at ON governance_role_domain;
CREATE TRIGGER trg_governance_role_domain_updated_at
    BEFORE UPDATE ON governance_role_domain
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_governance_role_policy_updated_at ON governance_role_policy;
CREATE TRIGGER trg_governance_role_policy_updated_at
    BEFORE UPDATE ON governance_role_policy
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_governance_role_assignment_updated_at ON governance_role_assignment;
CREATE TRIGGER trg_governance_role_assignment_updated_at
    BEFORE UPDATE ON governance_role_assignment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE VIEW v_governance_role_assignments AS
SELECT
    a.id AS assignment_id,
    a.role_id,
    r.role_key,
    r.name AS role_name,
    r.circle_id,
    c.circle_key,
    a.party_id,
    p.display_name AS party_name,
    p.party_type,
    a.assignment_type,
    a.status,
    a.mandate,
    a.recusal_status,
    a.effective_from,
    a.effective_until,
    a.review_due_at,
    a.approved_by_party_id,
    approver.display_name AS approved_by_name
FROM governance_role_assignment a
JOIN governance_role r ON r.id = a.role_id
JOIN governance_circle c ON c.id = r.circle_id
JOIN party p ON p.id = a.party_id
LEFT JOIN party approver ON approver.id = a.approved_by_party_id;

COMMENT ON TABLE governance_role_domain IS 'Explicit authority domain and constraints for a Kokonut role';
COMMENT ON TABLE governance_role_policy IS 'Role-specific policy constraints, separate from operational instructions';
COMMENT ON TABLE governance_role_assignment IS 'Time-bounded party assignment to a role with human approval and recusal state';
COMMENT ON VIEW v_governance_role_assignments IS 'Internal role assignment view with party, circle, and approval context';
