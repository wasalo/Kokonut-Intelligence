-- ============================================================
-- 124_orientation.sql — Situation assessment and OODA orientation
-- ============================================================
-- Synthesizes CRISP scores, metric trends, anomaly counts, and
-- analytics outputs into a unified situational picture per location.

CREATE TABLE IF NOT EXISTS situation_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL,
    assessment_type VARCHAR(50) NOT NULL DEFAULT 'full'
        CHECK (assessment_type IN ('full', 'quick', 'deep', 'reassessment')),
    situation_grade VARCHAR(20) NOT NULL
        CHECK (situation_grade IN ('critical', 'warning', 'stable', 'flourishing')),
    composite_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    confidence_level VARCHAR(20) NOT NULL DEFAULT 'low'
        CHECK (confidence_level IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    evidence_maturity INTEGER NOT NULL DEFAULT 1
        CHECK (evidence_maturity BETWEEN 1 AND 6),
    crisp_rating VARCHAR(5),
    crisp_composite_score DOUBLE PRECISION,
    anomaly_count INTEGER NOT NULL DEFAULT 0,
    critical_anomaly_count INTEGER NOT NULL DEFAULT 0,
    metric_trend_summary JSONB NOT NULL DEFAULT '{}',
    dimension_summaries JSONB NOT NULL DEFAULT '{}',
    recommendations JSONB NOT NULL DEFAULT '[]',
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assessed_by VARCHAR(100) NOT NULL DEFAULT 'system',
    methodology_version VARCHAR(50) NOT NULL DEFAULT 'v1.0',
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'verified', 'superseded')),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_situation_assessment_location
    ON situation_assessment (location_id, assessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_situation_assessment_grade
    ON situation_assessment (situation_grade, assessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_situation_assessment_status
    ON situation_assessment (status, assessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_situation_assessment_time
    ON situation_assessment (assessed_at DESC);

CREATE TABLE IF NOT EXISTS assessment_signal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID NOT NULL REFERENCES situation_assessment(id) ON DELETE CASCADE,
    signal_type VARCHAR(50) NOT NULL
        CHECK (signal_type IN ('crisp_dimension', 'metric_trend', 'anomaly_cluster',
                               'analytics_output', 'external_event', 'user_input')),
    signal_key VARCHAR(100) NOT NULL,
    signal_value DOUBLE PRECISION,
    signal_text TEXT,
    signal_direction VARCHAR(10) NOT NULL DEFAULT 'neutral'
        CHECK (signal_direction IN ('positive', 'negative', 'neutral', 'mixed')),
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    source_table VARCHAR(100),
    source_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assessment_signal_assessment
    ON assessment_signal (assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_signal_type_key
    ON assessment_signal (signal_type, signal_key);

CREATE TABLE IF NOT EXISTS assessment_dimension (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID NOT NULL REFERENCES situation_assessment(id) ON DELETE CASCADE,
    dimension_key VARCHAR(50) NOT NULL,
    dimension_name VARCHAR(100) NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    trend VARCHAR(10) NOT NULL DEFAULT 'stable'
        CHECK (trend IN ('improving', 'stable', 'declining', 'volatile')),
    trend_delta DOUBLE PRECISION,
    signal_count INTEGER NOT NULL DEFAULT 0,
    confidence_level VARCHAR(20) NOT NULL DEFAULT 'low'
        CHECK (confidence_level IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    evidence_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assessment_dimension_assessment
    ON assessment_dimension (assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_dimension_key
    ON assessment_dimension (dimension_key, risk_score);
