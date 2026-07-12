-- ============================================================
-- 130_double_loop.sql — Double-loop learning infrastructure
-- ============================================================

CREATE TABLE IF NOT EXISTS structural_question (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text TEXT NOT NULL,
    location_id UUID,
    domain VARCHAR(50) NOT NULL DEFAULT 'farm',
    trigger_reason VARCHAR(100) NOT NULL,
    trigger_source_id UUID,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'investigating', 'answered', 'deferred')),
    answer_text TEXT,
    answered_at TIMESTAMPTZ,
    answered_by VARCHAR(100),
    related_assumption_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_structural_question_location ON structural_question (location_id, status);
CREATE INDEX IF NOT EXISTS idx_structural_question_priority ON structural_question (priority, created_at DESC);

CREATE TABLE IF NOT EXISTS assumption_challenge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assumption_id UUID NOT NULL REFERENCES structural_assumption(id) ON DELETE CASCADE,
    challenge_text TEXT NOT NULL,
    evidence_type VARCHAR(50) NOT NULL
        CHECK (evidence_type IN ('metric_trend', 'archetype_detected', 'outcome_failure',
                                 'stakeholder_feedback', 'external_data', 'manual')),
    evidence_data JSONB NOT NULL DEFAULT '{}',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    challenged_by VARCHAR(100) NOT NULL DEFAULT 'system',
    challenged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assumption_challenge_assumption ON assumption_challenge (assumption_id);

CREATE TABLE IF NOT EXISTS paradigm_shift (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    from_paradigm VARCHAR(200) NOT NULL,
    to_paradigm VARCHAR(200) NOT NULL,
    shift_type VARCHAR(50) NOT NULL
        CHECK (shift_type IN ('worldview', 'methodology', 'goal', 'metric', 'governance')),
    evidence JSONB NOT NULL DEFAULT '{}',
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status VARCHAR(20) NOT NULL DEFAULT 'detected'
        CHECK (status IN ('detected', 'confirmed', 'dismissed')),
    confirmed_by VARCHAR(100),
    confirmed_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paradigm_shift_location ON paradigm_shift (location_id, status);
CREATE INDEX IF NOT EXISTS idx_paradigm_shift_type ON paradigm_shift (shift_type);
