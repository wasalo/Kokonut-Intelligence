-- ============================================================
-- 219_stakeholder_representation.sql - Participation and equity
-- ============================================================

CREATE TABLE IF NOT EXISTS stakeholder_participation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_type VARCHAR(40) NOT NULL CHECK (activity_type IN ('engagement_plan', 'touchpoint', 'delphi_study', 'decision', 'cooperative_meeting', 'feedback', 'other')),
    activity_id UUID NOT NULL,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    anonymous_group VARCHAR(120),
    stakeholder_role VARCHAR(80),
    invitation_status VARCHAR(20) NOT NULL DEFAULT 'invited'
        CHECK (invitation_status IN ('invited', 'accepted', 'declined', 'attended', 'absent', 'withdrawn')),
    invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    participated_at TIMESTAMPTZ,
    contribution_count INTEGER NOT NULL DEFAULT 0 CHECK (contribution_count >= 0),
    consent_checked BOOLEAN NOT NULL DEFAULT FALSE,
    access_needs_recorded BOOLEAN NOT NULL DEFAULT FALSE,
    language VARCHAR(80),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (activity_type, activity_id, party_id, anonymous_group),
    CHECK (party_id IS NOT NULL OR NULLIF(TRIM(COALESCE(anonymous_group, '')), '') IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_stp_activity ON stakeholder_participation(activity_type, activity_id);
CREATE INDEX IF NOT EXISTS idx_stp_party ON stakeholder_participation(party_id);
CREATE INDEX IF NOT EXISTS idx_stp_status ON stakeholder_participation(invitation_status);

CREATE TABLE IF NOT EXISTS stakeholder_accessibility_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participation_id UUID NOT NULL REFERENCES stakeholder_participation(id) ON DELETE CASCADE,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    need_type VARCHAR(40) NOT NULL CHECK (need_type IN ('language', 'channel', 'device', 'mobility', 'hearing', 'vision', 'literacy', 'schedule', 'privacy', 'other')),
    requested_support TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested', 'accepted', 'provided', 'declined', 'not_available')),
    provided_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sar_participation ON stakeholder_accessibility_request(participation_id, status);
CREATE INDEX IF NOT EXISTS idx_sar_party ON stakeholder_accessibility_request(party_id);

CREATE TABLE IF NOT EXISTS stakeholder_minority_view (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_type VARCHAR(40) NOT NULL,
    activity_id UUID NOT NULL,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    anonymous_group VARCHAR(120),
    view_summary TEXT NOT NULL,
    concern_or_risk TEXT,
    preserved BOOLEAN NOT NULL DEFAULT TRUE,
    decision_response TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (party_id IS NOT NULL OR NULLIF(TRIM(COALESCE(anonymous_group, '')), '') IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_smv_activity ON stakeholder_minority_view(activity_type, activity_id);
CREATE INDEX IF NOT EXISTS idx_smv_preserved ON stakeholder_minority_view(preserved);

CREATE TABLE IF NOT EXISTS stakeholder_distribution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type VARCHAR(30) NOT NULL CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'initiative', 'decision')),
    scope_id UUID,
    distribution_type VARCHAR(20) NOT NULL CHECK (distribution_type IN ('benefit', 'harm', 'cost', 'remedy')),
    beneficiary_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    stakeholder_type VARCHAR(40),
    metric_name VARCHAR(150) NOT NULL,
    amount NUMERIC NOT NULL,
    unit VARCHAR(80) NOT NULL,
    period_start DATE,
    period_end DATE,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES party(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_std_scope ON stakeholder_distribution(scope_type, scope_id, distribution_type);
CREATE INDEX IF NOT EXISTS idx_std_party ON stakeholder_distribution(beneficiary_party_id);
CREATE INDEX IF NOT EXISTS idx_std_status ON stakeholder_distribution(status);

CREATE OR REPLACE VIEW v_stakeholder_representation_metrics AS
SELECT
    sp.activity_type,
    sp.activity_id,
    COUNT(*) AS invited_count,
    COUNT(*) FILTER (WHERE sp.invitation_status IN ('accepted', 'attended')) AS accepted_count,
    COUNT(*) FILTER (WHERE sp.invitation_status = 'attended') AS participated_count,
    COUNT(*) FILTER (WHERE sp.invitation_status = 'declined') AS declined_count,
    COUNT(*) FILTER (WHERE sp.invitation_status = 'absent') AS absent_count,
    COUNT(*) FILTER (WHERE sp.contribution_count > 0) AS contributing_count,
    COUNT(*) FILTER (WHERE sp.access_needs_recorded) AS access_needs_count,
    COUNT(DISTINCT sar.id) AS accessibility_request_count,
    COUNT(DISTINCT smv.id) AS minority_view_count,
    COUNT(DISTINCT smv.id) FILTER (WHERE smv.preserved) AS minority_view_preserved_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE sp.invitation_status = 'attended') / NULLIF(COUNT(*), 0), 2) AS participation_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE sp.contribution_count > 0) / NULLIF(COUNT(*) FILTER (WHERE sp.invitation_status = 'attended'), 0), 2) AS contribution_rate_pct
FROM stakeholder_participation sp
LEFT JOIN stakeholder_accessibility_request sar ON sar.participation_id = sp.id
LEFT JOIN stakeholder_minority_view smv ON smv.activity_type = sp.activity_type AND smv.activity_id = sp.activity_id
GROUP BY sp.activity_type, sp.activity_id;

CREATE OR REPLACE VIEW v_public_stakeholder_representation AS
SELECT
    activity_type,
    activity_id,
    invited_count,
    participated_count,
    participation_rate_pct,
    contribution_rate_pct,
    minority_view_count,
    minority_view_preserved_count
FROM v_stakeholder_representation_metrics
WHERE invited_count >= 5;

CREATE OR REPLACE VIEW v_stakeholder_equity_distribution AS
SELECT
    sd.scope_type,
    sd.scope_id,
    sd.distribution_type,
    sd.metric_name,
    sd.unit,
    COUNT(*) AS record_count,
    COUNT(DISTINCT sd.beneficiary_party_id) AS beneficiary_count,
    SUM(sd.amount) AS total_amount,
    MIN(sd.period_start) AS earliest_period,
    MAX(sd.period_end) AS latest_period
FROM stakeholder_distribution sd
WHERE sd.status IN ('verified', 'published')
GROUP BY sd.scope_type, sd.scope_id, sd.distribution_type, sd.metric_name, sd.unit;

COMMENT ON TABLE stakeholder_participation IS 'Invitation and participation denominator for stakeholder representation metrics';
COMMENT ON TABLE stakeholder_accessibility_request IS 'Accessibility and inclusion support requests for participation';
COMMENT ON TABLE stakeholder_minority_view IS 'Dissenting or minority views preserved alongside aggregate decisions';
COMMENT ON TABLE stakeholder_distribution IS 'Evidence-backed benefit, harm, cost, and remedy distribution records';
COMMENT ON VIEW v_public_stakeholder_representation IS 'Public-safe participation metrics suppressed below five invitees';
