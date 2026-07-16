-- ============================================================
-- 281_strategy_consultation_communication.sql
-- Governed strategy consultation and communication workflows.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_consultation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    prompt TEXT NOT NULL,
    audience_type VARCHAR(30) NOT NULL CHECK (audience_type IN ('internal', 'farmer', 'stakeholder', 'mixed')),
    audience_scope_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'open', 'closed', 'synthesized', 'cancelled')),
    opens_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    synthesis JSONB,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (closes_at IS NULL OR opens_at IS NULL OR closes_at >= opens_at)
);

CREATE TABLE IF NOT EXISTS strategy_consultation_response (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES strategy_consultation(id) ON DELETE CASCADE,
    respondent_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    response TEXT NOT NULL,
    consent_checked BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'included', 'excluded', 'withdrawn')),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (consent_checked = TRUE OR status IN ('excluded', 'withdrawn'))
);

CREATE TABLE IF NOT EXISTS strategy_communication (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    audience_type VARCHAR(30) NOT NULL CHECK (audience_type IN ('internal', 'farmer', 'stakeholder', 'public')),
    channel VARCHAR(30) NOT NULL CHECK (channel IN ('email', 'sms', 'whatsapp', 'meeting', 'report', 'dashboard')),
    subject VARCHAR(255),
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'published', 'withdrawn')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status NOT IN ('approved', 'published') OR approved_at IS NOT NULL),
    CHECK (status <> 'published' OR published_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_strategy_consultation_plan
    ON strategy_consultation(strategy_plan_id, status, closes_at);
CREATE INDEX IF NOT EXISTS idx_strategy_consultation_response
    ON strategy_consultation_response(consultation_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_communication_plan
    ON strategy_communication(strategy_plan_id, status, created_at DESC);

DROP TRIGGER IF EXISTS trg_strategy_consultation_updated_at ON strategy_consultation;
CREATE TRIGGER trg_strategy_consultation_updated_at
    BEFORE UPDATE ON strategy_consultation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE strategy_consultation IS 'Private-by-default consultation prompts and governed response synthesis';
COMMENT ON TABLE strategy_communication IS 'Human-approved strategy communication drafts and publication records';
