-- ============================================================
-- 218_stakeholder_grievances.sql - Grievance and remedy workflow
-- ============================================================

CREATE TABLE IF NOT EXISTS stakeholder_grievance_case (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number VARCHAR(40) NOT NULL UNIQUE,
    feedback_id UUID REFERENCES stakeholder_feedback(id) ON DELETE SET NULL,
    complainant_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    affected_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    category VARCHAR(40) NOT NULL CHECK (category IN ('access', 'privacy', 'harm', 'safety', 'benefit', 'representation', 'conduct', 'environmental', 'other')),
    severity VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    confidentiality VARCHAR(20) NOT NULL DEFAULT 'restricted' CHECK (confidentiality IN ('private', 'restricted', 'internal')),
    status VARCHAR(25) NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'acknowledged', 'investigating', 'remedy_proposed', 'remedy_in_progress', 'resolved', 'appealed', 'closed', 'dismissed')),
    summary TEXT NOT NULL,
    protected_details TEXT,
    retaliation_risk BOOLEAN NOT NULL DEFAULT FALSE,
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    independent_reviewer_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    due_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    escalation_id UUID REFERENCES process_escalation(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (complainant_party_id IS NULL OR complainant_party_id <> owner_party_id),
    CHECK (independent_reviewer_party_id IS NULL OR independent_reviewer_party_id <> complainant_party_id)
);

CREATE INDEX IF NOT EXISTS idx_sgc_status ON stakeholder_grievance_case(status, severity);
CREATE INDEX IF NOT EXISTS idx_sgc_party ON stakeholder_grievance_case(complainant_party_id, affected_party_id);
CREATE INDEX IF NOT EXISTS idx_sgc_location ON stakeholder_grievance_case(location_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_sgc_due ON stakeholder_grievance_case(due_at)
    WHERE status NOT IN ('resolved', 'closed', 'dismissed');
CREATE INDEX IF NOT EXISTS idx_sgc_feedback ON stakeholder_grievance_case(feedback_id);

CREATE TABLE IF NOT EXISTS grievance_investigation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES stakeholder_grievance_case(id) ON DELETE CASCADE,
    investigator_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    conflict_check_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (conflict_check_status IN ('pending', 'clear', 'conflict', 'waived')),
    status VARCHAR(20) NOT NULL DEFAULT 'assigned'
        CHECK (status IN ('assigned', 'in_progress', 'complete', 'cancelled')),
    scope TEXT NOT NULL,
    findings TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (conflict_check_status <> 'conflict' OR status = 'cancelled')
);

CREATE INDEX IF NOT EXISTS idx_gi_case ON grievance_investigation(case_id, status);
CREATE INDEX IF NOT EXISTS idx_gi_investigator ON grievance_investigation(investigator_party_id, status);

CREATE TABLE IF NOT EXISTS grievance_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES stakeholder_grievance_case(id) ON DELETE CASCADE,
    investigation_id UUID REFERENCES grievance_investigation(id) ON DELETE SET NULL,
    evidence_type VARCHAR(30) NOT NULL CHECK (evidence_type IN ('document', 'image', 'audio', 'video', 'statement', 'record', 'other')),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    content_hash VARCHAR(128),
    content_cid TEXT,
    submitted_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    confidentiality VARCHAR(20) NOT NULL DEFAULT 'restricted' CHECK (confidentiality IN ('private', 'restricted', 'internal')),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ge_case ON grievance_evidence(case_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_ge_investigation ON grievance_evidence(investigation_id);

CREATE TABLE IF NOT EXISTS grievance_remedy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES stakeholder_grievance_case(id) ON DELETE CASCADE,
    remedy_type VARCHAR(30) NOT NULL CHECK (remedy_type IN ('explanation', 'correction', 'restitution', 'restoration', 'prevention', 'apology', 'referral', 'other')),
    proposal TEXT NOT NULL,
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    due_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'accepted', 'in_progress', 'completed', 'rejected', 'waived')),
    affected_party_confirmed BOOLEAN,
    completion_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gr_case ON grievance_remedy(case_id, status);
CREATE INDEX IF NOT EXISTS idx_gr_due ON grievance_remedy(due_at) WHERE status IN ('accepted', 'in_progress');

CREATE TABLE IF NOT EXISTS grievance_appeal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES stakeholder_grievance_case(id) ON DELETE CASCADE,
    appealed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'reviewing', 'upheld', 'overturned', 'closed')),
    reviewer_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    conflict_check_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (conflict_check_status IN ('pending', 'clear', 'conflict', 'waived')),
    decision_notes TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (reviewer_party_id IS NULL OR reviewer_party_id <> appealed_by_party_id)
);

CREATE INDEX IF NOT EXISTS idx_ga_case ON grievance_appeal(case_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_ga_status ON grievance_appeal(status);

CREATE TABLE IF NOT EXISTS grievance_closure (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL UNIQUE REFERENCES stakeholder_grievance_case(id) ON DELETE CASCADE,
    closure_reason TEXT NOT NULL,
    satisfaction_score NUMERIC(4,2) CHECK (satisfaction_score BETWEEN 0 AND 10),
    complainant_confirmed BOOLEAN,
    independent_review_completed BOOLEAN NOT NULL DEFAULT FALSE,
    closure_notes TEXT,
    closed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    closed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE OR REPLACE VIEW v_stakeholder_grievance_health AS
SELECT
    gc.id AS case_id,
    gc.case_number,
    gc.category,
    gc.severity,
    gc.confidentiality,
    gc.status,
    gc.summary,
    gc.location_id,
    cp.display_name AS complainant_name,
    ap.display_name AS affected_party_name,
    op.display_name AS owner_name,
    gc.received_at,
    gc.due_at,
    gc.work_item_id,
    COUNT(DISTINCT gi.id) AS investigation_count,
    COUNT(DISTINCT ge.id) AS evidence_count,
    COUNT(DISTINCT gr.id) AS remedy_count,
    COUNT(DISTINCT gr.id) FILTER (WHERE gr.status IN ('proposed', 'accepted', 'in_progress')) AS open_remedy_count,
    COUNT(DISTINCT ga.id) AS appeal_count,
    closure.satisfaction_score,
    CASE
        WHEN gc.status NOT IN ('resolved', 'closed', 'dismissed') AND gc.due_at IS NOT NULL AND gc.due_at < NOW() THEN TRUE
        ELSE FALSE
    END AS is_overdue
FROM stakeholder_grievance_case gc
LEFT JOIN party cp ON cp.id = gc.complainant_party_id
LEFT JOIN party ap ON ap.id = gc.affected_party_id
LEFT JOIN party op ON op.id = gc.owner_party_id
LEFT JOIN grievance_investigation gi ON gi.case_id = gc.id
LEFT JOIN grievance_evidence ge ON ge.case_id = gc.id
LEFT JOIN grievance_remedy gr ON gr.case_id = gc.id
LEFT JOIN grievance_appeal ga ON ga.case_id = gc.id
LEFT JOIN grievance_closure closure ON closure.case_id = gc.id
GROUP BY gc.id, gc.case_number, gc.category, gc.severity, gc.confidentiality,
         gc.status, gc.summary, gc.location_id, cp.display_name, ap.display_name,
         op.display_name, gc.received_at, gc.due_at, gc.work_item_id,
         closure.satisfaction_score;

COMMENT ON TABLE stakeholder_grievance_case IS 'Protected stakeholder complaint and harm case with investigation, remedy, appeal, and closure controls';
COMMENT ON TABLE grievance_evidence IS 'Confidential evidence records for grievance investigations';
COMMENT ON TABLE grievance_remedy IS 'Tracked remedies and affected-party confirmation';
COMMENT ON VIEW v_stakeholder_grievance_health IS 'Internal grievance status, remedy, appeal, and SLA health; not a public view';
