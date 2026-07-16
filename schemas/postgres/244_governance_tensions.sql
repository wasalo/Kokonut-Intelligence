-- ============================================================
-- 244_governance_tensions.sql
-- Observable coordination gaps and triage state.
-- ============================================================

CREATE TABLE IF NOT EXISTS governance_tension (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tension_key VARCHAR(120) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    tension_type VARCHAR(40) NOT NULL CHECK (tension_type IN (
        'unmet_interest', 'unclear_accountability', 'authority_gap',
        'authority_conflict', 'commitment_risk', 'representation_gap',
        'consent_gap', 'evidence_gap', 'harm_risk', 'policy_gap',
        'cross_circle_dependency', 'role_overload'
    )),
    severity SMALLINT NOT NULL DEFAULT 3 CHECK (severity BETWEEN 1 AND 5),
    urgency SMALLINT NOT NULL DEFAULT 3 CHECK (urgency BETWEEN 1 AND 5),
    circle_id UUID REFERENCES governance_circle(id) ON DELETE SET NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    reported_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    affected_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    affected_interest_id UUID REFERENCES stakeholder_interest(id) ON DELETE SET NULL,
    owner_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    decision_id UUID REFERENCES stakeholder_decision(id) ON DELETE SET NULL,
    grievance_id UUID REFERENCES stakeholder_grievance_case(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'triaged', 'in_progress', 'resolved', 'deferred', 'rejected', 'closed')),
    resolution_summary TEXT,
    deferred_until TIMESTAMPTZ,
    review_due_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status NOT IN ('resolved', 'closed') OR NULLIF(BTRIM(resolution_summary), '') IS NOT NULL),
    CHECK (status <> 'deferred' OR deferred_until IS NOT NULL),
    CHECK (owner_role_id IS NOT NULL OR owner_party_id IS NOT NULL OR status IN ('draft', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_governance_tension_circle
    ON governance_tension(circle_id, status, severity DESC, urgency DESC);
CREATE INDEX IF NOT EXISTS idx_governance_tension_scope
    ON governance_tension(scope_type, scope_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_tension_owner
    ON governance_tension(owner_party_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_tension_role_owner
    ON governance_tension(owner_role_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_tension_review
    ON governance_tension(review_due_at)
    WHERE status IN ('submitted', 'triaged', 'in_progress', 'deferred');

CREATE TABLE IF NOT EXISTS governance_tension_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tension_id UUID NOT NULL REFERENCES governance_tension(id) ON DELETE CASCADE,
    link_type VARCHAR(30) NOT NULL CHECK (link_type IN (
        'interest', 'commitment', 'work_item', 'decision', 'grievance',
        'evidence', 'relationship', 'proposal', 'outcome'
    )),
    entity_type VARCHAR(80) NOT NULL,
    entity_id UUID NOT NULL,
    summary TEXT,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tension_id, link_type, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_governance_tension_link_entity
    ON governance_tension_link(entity_type, entity_id, link_type);
CREATE INDEX IF NOT EXISTS idx_governance_tension_link_tension
    ON governance_tension_link(tension_id, link_type);

CREATE TABLE IF NOT EXISTS governance_tension_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tension_id UUID NOT NULL REFERENCES governance_tension(id) ON DELETE CASCADE,
    actor_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    action VARCHAR(60) NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_governance_tension_event_tension
    ON governance_tension_event(tension_id, created_at);

CREATE OR REPLACE VIEW v_governance_tension_health AS
SELECT
    t.id AS tension_id,
    t.tension_key,
    t.title,
    t.description,
    t.tension_type,
    t.severity,
    t.urgency,
    t.circle_id,
    c.circle_key,
    c.name AS circle_name,
    t.scope_type,
    t.scope_id,
    t.status,
    t.reported_by_party_id,
    reporter.display_name AS reported_by_name,
    t.affected_party_id,
    affected.display_name AS affected_party_name,
    t.owner_role_id,
    r.role_key AS owner_role_key,
    t.owner_party_id,
    owner_party.display_name AS owner_party_name,
    t.work_item_id,
    t.decision_id,
    t.grievance_id,
    t.review_due_at,
    t.deferred_until,
    COUNT(l.id) AS link_count,
    CASE WHEN t.review_due_at IS NOT NULL AND t.review_due_at < NOW()
         AND t.status IN ('submitted', 'triaged', 'in_progress', 'deferred')
         THEN TRUE ELSE FALSE END AS is_overdue
FROM governance_tension t
LEFT JOIN governance_circle c ON c.id = t.circle_id
LEFT JOIN party reporter ON reporter.id = t.reported_by_party_id
LEFT JOIN party affected ON affected.id = t.affected_party_id
LEFT JOIN governance_role r ON r.id = t.owner_role_id
LEFT JOIN party owner_party ON owner_party.id = t.owner_party_id
LEFT JOIN governance_tension_link l ON l.tension_id = t.id
GROUP BY t.id, t.tension_key, t.title, t.description, t.tension_type,
         t.severity, t.urgency, t.circle_id, c.circle_key, c.name,
         t.scope_type, t.scope_id, t.status, t.reported_by_party_id,
         reporter.display_name, t.affected_party_id, affected.display_name,
         t.owner_role_id, r.role_key, t.owner_party_id, owner_party.display_name,
         t.work_item_id, t.decision_id, t.grievance_id, t.review_due_at,
         t.deferred_until;

DROP TRIGGER IF EXISTS trg_governance_tension_updated_at ON governance_tension;
CREATE TRIGGER trg_governance_tension_updated_at
    BEFORE UPDATE ON governance_tension
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE governance_tension IS 'Evidence-backed coordination gap requiring triage, action, or governance change';
COMMENT ON TABLE governance_tension_link IS 'Typed links from a tension to stakeholder, execution, evidence, and governance records';
COMMENT ON TABLE governance_tension_event IS 'Append-only tension lifecycle history';
COMMENT ON VIEW v_governance_tension_health IS 'Internal tension triage, ownership, linkage, and overdue health';
