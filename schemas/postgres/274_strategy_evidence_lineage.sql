-- ============================================================
-- 274_strategy_evidence_lineage.sql
-- Typed source lineage for strategic planning artifacts.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_evidence_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    subject_type VARCHAR(30) NOT NULL CHECK (subject_type IN ('plan', 'choice', 'assumption', 'position', 'advantage', 'objective', 'investment', 'benefit')),
    subject_id UUID NOT NULL,
    source_type VARCHAR(40) NOT NULL CHECK (source_type IN ('pestel_factor', 'swot_factor', 'competitive_signal', 'competitive_force', 'scenario', 'threat_signal', 'stakeholder_outcome', 'crisp_assessment', 'metric_value', 'capability', 'market_segment', 'external_document')),
    source_id UUID,
    source_ref TEXT,
    relevance VARCHAR(20) NOT NULL DEFAULT 'supporting' CHECK (relevance IN ('supporting', 'contradicting', 'contextual', 'required')),
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate' CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    evidence_maturity INTEGER REFERENCES evidence_maturity_level(level),
    source_version VARCHAR(100),
    interpretation TEXT,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (strategy_plan_id, subject_type, subject_id, source_type, source_id, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_strategy_evidence_subject ON strategy_evidence_link(strategy_plan_id, subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_strategy_evidence_source ON strategy_evidence_link(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_strategy_evidence_quality ON strategy_evidence_link(confidence, evidence_maturity, relevance);

COMMENT ON TABLE strategy_evidence_link IS 'Typed, reviewed lineage connecting strategic planning artifacts to governed evidence sources';
