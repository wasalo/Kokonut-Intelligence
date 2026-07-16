-- ============================================================
-- 253_operating_coaching_resources.sql
-- Protected coaching and governed resource requests.
-- ============================================================

CREATE TABLE IF NOT EXISTS operating_coaching_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('internal', 'adelphi')),
    scope_id UUID NOT NULL,
    coachee_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    coach_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,
    focus VARCHAR(255) NOT NULL,
    commitments JSONB NOT NULL DEFAULT '[]'::jsonb,
    wellbeing_check TEXT,
    notes TEXT,
    privacy_level VARCHAR(20) NOT NULL DEFAULT 'private'
        CHECK (privacy_level IN ('private', 'limited', 'aggregate_only')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operating_coaching_coachee
    ON operating_coaching_session(coachee_party_id, session_date DESC);
CREATE INDEX IF NOT EXISTS idx_operating_coaching_scope
    ON operating_coaching_session(scope_type, scope_id, session_date DESC);

CREATE TABLE IF NOT EXISTS operating_resource_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('internal', 'adelphi')),
    scope_id UUID NOT NULL,
    requested_by_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    urgency VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (urgency IN ('low', 'medium', 'high', 'critical')),
    requested_by DATE NOT NULL,
    decision VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (decision IN ('pending', 'approved', 'partially_approved', 'declined', 'fulfilled')),
    decision_reason TEXT,
    decided_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('draft', 'submitted', 'reviewed', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (decision = 'pending' OR decided_by_party_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_operating_resource_request_scope
    ON operating_resource_request(scope_type, scope_id, decision, urgency);
CREATE INDEX IF NOT EXISTS idx_operating_resource_request_party
    ON operating_resource_request(requested_by_party_id, status);

DROP TRIGGER IF EXISTS trg_operating_coaching_updated_at ON operating_coaching_session;
CREATE TRIGGER trg_operating_coaching_updated_at BEFORE UPDATE ON operating_coaching_session
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_operating_resource_updated_at ON operating_resource_request;
CREATE TRIGGER trg_operating_resource_updated_at BEFORE UPDATE ON operating_resource_request
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
