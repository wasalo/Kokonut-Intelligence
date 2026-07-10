-- ============================================================
-- 093_ai_evaluation.sql — AI-Powered Impact Evaluation
-- ============================================================

-- 1. AI impact evaluation
CREATE TABLE IF NOT EXISTS ai_impact_evaluation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    evaluation_type VARCHAR(100) NOT NULL,
    period_start DATE,
    period_end DATE,
    impact_score NUMERIC(12,4),
    confidence NUMERIC(5,4),
    methodology VARCHAR(255),
    evidence_sources TEXT[],
    agent_outputs JSONB,
    human_validator_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    human_validation_result VARCHAR(50),
    human_validation_notes TEXT,
    validated_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'ai_generated',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS aie_location ON ai_impact_evaluation(location_id);
CREATE INDEX IF NOT EXISTS aie_type ON ai_impact_evaluation(evaluation_type);
CREATE INDEX IF NOT EXISTS aie_status ON ai_impact_evaluation(status);

ALTER TABLE ai_impact_evaluation DROP CONSTRAINT IF EXISTS chk_aie_status;
ALTER TABLE ai_impact_evaluation ADD CONSTRAINT chk_aie_status CHECK (status IN (
    'ai_generated', 'pending_validation', 'validated', 'rejected', 'superseded'
));

ALTER TABLE ai_impact_evaluation DROP CONSTRAINT IF EXISTS chk_aie_validation;
ALTER TABLE ai_impact_evaluation ADD CONSTRAINT chk_aie_validation CHECK (
    human_validation_result IS NULL OR human_validation_result IN ('approved', 'rejected', 'needs_revision')
);
