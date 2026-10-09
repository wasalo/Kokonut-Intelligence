-- ============================================================
-- 216_stakeholder_engagement.sql - Engagement and commitments
-- ============================================================

CREATE TABLE IF NOT EXISTS stakeholder_engagement_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    stakeholder_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organization(id) ON DELETE SET NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    engagement_mode VARCHAR(30) NOT NULL DEFAULT 'collaborate'
        CHECK (engagement_mode IN ('inform', 'consult', 'involve', 'collaborate', 'empower', 'steward')),
    cadence_days INTEGER CHECK (cadence_days > 0),
    next_review_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'paused', 'completed', 'cancelled')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sep_party ON stakeholder_engagement_plan(stakeholder_party_id, status);
CREATE INDEX IF NOT EXISTS idx_sep_owner ON stakeholder_engagement_plan(owner_party_id, status);
CREATE INDEX IF NOT EXISTS idx_sep_scope ON stakeholder_engagement_plan(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_sep_review ON stakeholder_engagement_plan(next_review_at)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS stakeholder_engagement_objective (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES stakeholder_engagement_plan(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    desired_outcome TEXT NOT NULL,
    success_metric VARCHAR(150),
    target_value NUMERIC,
    unit VARCHAR(50),
    target_date DATE,
    priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'active', 'met', 'deferred', 'retired')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seo_plan ON stakeholder_engagement_objective(plan_id, status);

CREATE TABLE IF NOT EXISTS stakeholder_touchpoint (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES stakeholder_engagement_plan(id) ON DELETE CASCADE,
    objective_id UUID REFERENCES stakeholder_engagement_objective(id) ON DELETE SET NULL,
    channel_type VARCHAR(50),
    interaction_type VARCHAR(80) NOT NULL DEFAULT 'engagement',
    purpose TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'scheduled', 'completed', 'missed', 'cancelled')),
    customer_interaction_id UUID REFERENCES customer_interaction(id) ON DELETE SET NULL,
    consent_checked BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_set_plan ON stakeholder_touchpoint(plan_id, status);
CREATE INDEX IF NOT EXISTS idx_set_schedule ON stakeholder_touchpoint(scheduled_at, status);
CREATE INDEX IF NOT EXISTS idx_set_interaction ON stakeholder_touchpoint(customer_interaction_id);

CREATE TABLE IF NOT EXISTS stakeholder_commitment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES stakeholder_engagement_plan(id) ON DELETE CASCADE,
    objective_id UUID REFERENCES stakeholder_engagement_objective(id) ON DELETE SET NULL,
    touchpoint_id UUID REFERENCES stakeholder_touchpoint(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    committed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    committed_to_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    due_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'fulfilled', 'overdue', 'waived', 'cancelled')),
    work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    responsibility_id UUID REFERENCES responsibility_assignment(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (committed_by_party_id IS NULL OR committed_to_party_id IS NULL OR committed_by_party_id <> committed_to_party_id)
);

CREATE INDEX IF NOT EXISTS idx_sec_plan ON stakeholder_commitment(plan_id, status);
CREATE INDEX IF NOT EXISTS idx_sec_owner ON stakeholder_commitment(owner_party_id, status);
CREATE INDEX IF NOT EXISTS idx_sec_due ON stakeholder_commitment(due_at)
    WHERE status IN ('open', 'in_progress', 'overdue');
CREATE INDEX IF NOT EXISTS idx_sec_work_item ON stakeholder_commitment(work_item_id);
CREATE INDEX IF NOT EXISTS idx_sec_responsibility ON stakeholder_commitment(responsibility_id);

CREATE TABLE IF NOT EXISTS stakeholder_engagement_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES stakeholder_engagement_plan(id) ON DELETE CASCADE,
    objective_id UUID REFERENCES stakeholder_engagement_objective(id) ON DELETE SET NULL,
    commitment_id UUID REFERENCES stakeholder_commitment(id) ON DELETE SET NULL,
    outcome_type VARCHAR(30) NOT NULL CHECK (outcome_type IN ('progress', 'benefit', 'harm', 'feedback', 'resolution', 'relationship_change')),
    outcome_summary TEXT NOT NULL,
    satisfaction_score NUMERIC(4,2) CHECK (satisfaction_score BETWEEN 0 AND 10),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_by UUID REFERENCES party(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_see_plan ON stakeholder_engagement_outcome(plan_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_see_commitment ON stakeholder_engagement_outcome(commitment_id);

CREATE OR REPLACE VIEW v_stakeholder_commitment_health AS
SELECT
    c.id AS commitment_id,
    c.plan_id,
    p.name AS plan_name,
    sp.display_name AS stakeholder_name,
    op.display_name AS owner_name,
    c.title,
    c.status,
    c.due_at,
    c.work_item_id,
    wi.status::text AS work_item_status,
    c.responsibility_id,
    CASE
        WHEN c.status IN ('open', 'in_progress') AND c.due_at IS NOT NULL AND c.due_at < NOW() THEN TRUE
        ELSE FALSE
    END AS is_overdue,
    COUNT(o.id) AS outcome_count,
    MAX(o.recorded_at) AS last_outcome_at
FROM stakeholder_commitment c
JOIN stakeholder_engagement_plan p ON p.id = c.plan_id
JOIN party sp ON sp.id = p.stakeholder_party_id
LEFT JOIN party op ON op.id = c.owner_party_id
LEFT JOIN work_item wi ON wi.id = c.work_item_id
LEFT JOIN stakeholder_engagement_outcome o ON o.commitment_id = c.id
GROUP BY c.id, c.plan_id, p.name, sp.display_name, op.display_name, c.title,
         c.status, c.due_at, c.work_item_id, wi.status, c.responsibility_id;

CREATE OR REPLACE VIEW v_stakeholder_engagement_summary AS
SELECT
    p.id AS plan_id,
    p.name,
    p.status,
    p.engagement_mode,
    sp.id AS stakeholder_party_id,
    sp.display_name AS stakeholder_name,
    COUNT(DISTINCT o.id) AS objective_count,
    COUNT(DISTINCT t.id) AS touchpoint_count,
    COUNT(DISTINCT c.id) AS commitment_count,
    COUNT(DISTINCT c.id) FILTER (WHERE c.status IN ('open', 'in_progress')) AS open_commitment_count,
    COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'fulfilled') AS fulfilled_commitment_count,
    COUNT(DISTINCT c.id) FILTER (WHERE c.status IN ('open', 'in_progress') AND c.due_at < NOW()) AS overdue_commitment_count,
    COUNT(DISTINCT e.id) AS outcome_count,
    MAX(e.recorded_at) AS last_outcome_at
FROM stakeholder_engagement_plan p
JOIN party sp ON sp.id = p.stakeholder_party_id
LEFT JOIN stakeholder_engagement_objective o ON o.plan_id = p.id
LEFT JOIN stakeholder_touchpoint t ON t.plan_id = p.id
LEFT JOIN stakeholder_commitment c ON c.plan_id = p.id
LEFT JOIN stakeholder_engagement_outcome e ON e.plan_id = p.id
GROUP BY p.id, p.name, p.status, p.engagement_mode, sp.id, sp.display_name;

COMMENT ON TABLE stakeholder_engagement_plan IS 'Governed engagement relationship plan for a canonical stakeholder party';
COMMENT ON TABLE stakeholder_commitment IS 'Actionable commitments linked to optional work items and RACI assignments';
COMMENT ON VIEW v_stakeholder_commitment_health IS 'Commitment SLA and execution health for engagement escalation';
