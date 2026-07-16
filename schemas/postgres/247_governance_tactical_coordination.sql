-- ============================================================
-- 247_governance_tactical_coordination.sql
-- Structured operational triage for governance circles.
-- ============================================================

CREATE TABLE IF NOT EXISTS governance_tactical_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circle_id UUID NOT NULL REFERENCES governance_circle(id) ON DELETE RESTRICT,
    session_type VARCHAR(30) NOT NULL CHECK (session_type IN (
        'weekly_review', 'stakeholder_health', 'relationship_review',
        'risk_triage', 'governance_followup'
    )),
    title VARCHAR(255) NOT NULL,
    scheduled_at TIMESTAMPTZ,
    facilitator_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    recorder_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'active', 'completed', 'cancelled')),
    agenda_scope TEXT,
    notes TEXT,
    outcome_summary TEXT,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'completed' OR NULLIF(BTRIM(outcome_summary), '') IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_governance_tactical_session_circle
    ON governance_tactical_session(circle_id, status, scheduled_at);

CREATE TABLE IF NOT EXISTS governance_tactical_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES governance_tactical_session(id) ON DELETE CASCADE,
    tension_id UUID REFERENCES governance_tension(id) ON DELETE SET NULL,
    work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    decision_id UUID REFERENCES stakeholder_decision(id) ON DELETE SET NULL,
    proposer_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    owner_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    requested_next_action TEXT NOT NULL,
    priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    due_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'disposed', 'cancelled')),
    disposition_type VARCHAR(30)
        CHECK (disposition_type IN ('next_action', 'delegate', 'create_work_item', 'create_proposal', 'escalate', 'defer', 'no_action')),
    disposition_summary TEXT,
    disposed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    disposed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (owner_role_id IS NOT NULL OR owner_party_id IS NOT NULL OR status IN ('open', 'cancelled')),
    CHECK (status <> 'disposed' OR disposition_type IS NOT NULL),
    CHECK (status <> 'disposed' OR NULLIF(BTRIM(disposition_summary), '') IS NOT NULL),
    CHECK (status <> 'disposed' OR disposed_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_governance_tactical_item_session
    ON governance_tactical_item(session_id, status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_governance_tactical_item_owner
    ON governance_tactical_item(owner_party_id, status);
CREATE INDEX IF NOT EXISTS idx_governance_tactical_item_tension
    ON governance_tactical_item(tension_id);

DROP TRIGGER IF EXISTS trg_governance_tactical_session_updated_at ON governance_tactical_session;
CREATE TRIGGER trg_governance_tactical_session_updated_at
    BEFORE UPDATE ON governance_tactical_session
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_governance_tactical_item_updated_at ON governance_tactical_item;
CREATE TRIGGER trg_governance_tactical_item_updated_at
    BEFORE UPDATE ON governance_tactical_item
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE VIEW v_governance_tactical_health AS
SELECT
    s.id AS session_id,
    s.circle_id,
    c.circle_key,
    s.session_type,
    s.title,
    s.scheduled_at,
    s.status AS session_status,
    COUNT(i.id) AS item_count,
    COUNT(i.id) FILTER (WHERE i.status IN ('open', 'in_progress')) AS open_item_count,
    COUNT(i.id) FILTER (WHERE i.status = 'disposed') AS disposed_item_count,
    COUNT(i.id) FILTER (WHERE i.status IN ('open', 'in_progress') AND i.due_at < NOW()) AS overdue_item_count
FROM governance_tactical_session s
JOIN governance_circle c ON c.id = s.circle_id
LEFT JOIN governance_tactical_item i ON i.session_id = s.id
GROUP BY s.id, s.circle_id, c.circle_key, s.session_type, s.title,
         s.scheduled_at, s.status;

COMMENT ON TABLE governance_tactical_session IS 'Structured tactical review session for one bounded governance circle';
COMMENT ON TABLE governance_tactical_item IS 'Concrete agenda item and disposition linked to tensions, work, or decisions';
COMMENT ON VIEW v_governance_tactical_health IS 'Internal tactical session throughput and overdue action health';
