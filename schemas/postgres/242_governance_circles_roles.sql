-- ============================================================
-- 242_governance_circles_roles.sql
-- Kokonut-native role and circle registry.
-- ============================================================

CREATE TABLE IF NOT EXISTS governance_circle (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circle_key VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    purpose TEXT NOT NULL,
    description TEXT,
    parent_circle_id UUID REFERENCES governance_circle(id) ON DELETE RESTRICT,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'active', 'suspended', 'retired', 'rejected')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    review_due_at TIMESTAMPTZ,
    retired_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (id <> parent_circle_id),
    CHECK (status <> 'active' OR NULLIF(BTRIM(purpose), '') IS NOT NULL),
    CHECK (status <> 'retired' OR retired_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_governance_circle_parent
    ON governance_circle(parent_circle_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_circle_scope
    ON governance_circle(scope_type, scope_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_circle_review
    ON governance_circle(review_due_at)
    WHERE status IN ('submitted', 'active');

CREATE TABLE IF NOT EXISTS governance_role (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circle_id UUID NOT NULL REFERENCES governance_circle(id) ON DELETE RESTRICT,
    role_key VARCHAR(120) NOT NULL,
    name VARCHAR(255) NOT NULL,
    purpose TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'active', 'suspended', 'retired', 'rejected')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    effective_from TIMESTAMPTZ,
    effective_until TIMESTAMPTZ,
    review_due_at TIMESTAMPTZ,
    supersedes_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (circle_id, role_key),
    CHECK (status NOT IN ('approved', 'active') OR NULLIF(BTRIM(purpose), '') IS NOT NULL),
    CHECK (effective_until IS NULL OR effective_from IS NULL OR effective_until >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_governance_role_circle
    ON governance_role(circle_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_role_review
    ON governance_role(review_due_at)
    WHERE status IN ('submitted', 'approved', 'active');

CREATE TABLE IF NOT EXISTS governance_role_accountability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES governance_role(id) ON DELETE CASCADE,
    accountability TEXT NOT NULL,
    priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    required BOOLEAN NOT NULL DEFAULT TRUE,
    evidence_expectation TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('draft', 'active', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (role_id, accountability)
);

CREATE INDEX IF NOT EXISTS idx_governance_role_accountability_role
    ON governance_role_accountability(role_id, status, priority);

CREATE OR REPLACE VIEW v_governance_circle_registry AS
SELECT
    c.id AS circle_id,
    c.circle_key,
    c.name,
    c.purpose,
    c.parent_circle_id,
    parent.circle_key AS parent_circle_key,
    c.scope_type,
    c.scope_id,
    c.status,
    c.review_due_at,
    COUNT(r.id) FILTER (WHERE r.status IN ('approved', 'active')) AS active_role_count,
    COUNT(r.id) FILTER (WHERE r.status IN ('approved', 'active') AND r.review_due_at < NOW()) AS overdue_role_review_count
FROM governance_circle c
LEFT JOIN governance_circle parent ON parent.id = c.parent_circle_id
LEFT JOIN governance_role r ON r.circle_id = c.id
GROUP BY c.id, c.circle_key, c.name, c.purpose, c.parent_circle_id,
         parent.circle_key, c.scope_type, c.scope_id, c.status, c.review_due_at;

CREATE OR REPLACE VIEW v_governance_role_registry AS
SELECT
    r.id AS role_id,
    r.circle_id,
    c.circle_key,
    c.name AS circle_name,
    r.role_key,
    r.name,
    r.purpose,
    r.status,
    r.effective_from,
    r.effective_until,
    r.review_due_at,
    COUNT(a.id) FILTER (WHERE a.status = 'active') AS accountability_count,
    COUNT(a.id) FILTER (WHERE a.status = 'active' AND a.required) AS required_accountability_count
FROM governance_role r
JOIN governance_circle c ON c.id = r.circle_id
LEFT JOIN governance_role_accountability a ON a.role_id = r.id
GROUP BY r.id, r.circle_id, c.circle_key, c.name, r.role_key, r.name,
         r.purpose, r.status, r.effective_from, r.effective_until, r.review_due_at;

DROP TRIGGER IF EXISTS trg_governance_circle_updated_at ON governance_circle;
CREATE TRIGGER trg_governance_circle_updated_at
    BEFORE UPDATE ON governance_circle
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_governance_role_updated_at ON governance_role;
CREATE TRIGGER trg_governance_role_updated_at
    BEFORE UPDATE ON governance_role
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE governance_circle IS 'Bounded Kokonut governance or operating circle with explicit purpose and scope';
COMMENT ON TABLE governance_role IS 'Role purpose and lifecycle independent of the party temporarily filling it';
COMMENT ON TABLE governance_role_accountability IS 'Queryable ongoing accountabilities for a governance role';
COMMENT ON VIEW v_governance_circle_registry IS 'Internal circle registry with role coverage and review health';
COMMENT ON VIEW v_governance_role_registry IS 'Internal role registry with accountability coverage';
