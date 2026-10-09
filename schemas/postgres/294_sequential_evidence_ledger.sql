-- ============================================================
-- 294_sequential_evidence_ledger.sql
-- Immutable hypotheses and sequential evidence events.
-- ============================================================

CREATE TABLE IF NOT EXISTS decision_hypothesis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type VARCHAR(40) NOT NULL,
    subject_id UUID NOT NULL,
    statement TEXT NOT NULL,
    alternative_statement TEXT NOT NULL,
    prior_probability NUMERIC(12,10) NOT NULL CHECK (prior_probability > 0 AND prior_probability < 1),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('draft', 'active', 'resolved', 'retired')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS decision_evidence_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES decision_hypothesis(id) ON DELETE CASCADE,
    source_type VARCHAR(40) NOT NULL,
    source_id UUID,
    source_ref TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence_class VARCHAR(40) NOT NULL,
    value JSONB NOT NULL DEFAULT '{}',
    quality_status VARCHAR(20) NOT NULL DEFAULT 'unverified'
        CHECK (quality_status IN ('unverified', 'provisional', 'verified', 'rejected', 'stale')),
    source_reliability NUMERIC(6,5) CHECK (source_reliability IS NULL OR source_reliability BETWEEN 0 AND 1),
    dependence_group VARCHAR(120),
    likelihood_hypothesis NUMERIC(15,10) CHECK (likelihood_hypothesis IS NULL OR likelihood_hypothesis > 0),
    likelihood_alternative NUMERIC(15,10) CHECK (likelihood_alternative IS NULL OR likelihood_alternative > 0),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_posterior_update (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES decision_hypothesis(id) ON DELETE CASCADE,
    evidence_event_id UUID NOT NULL REFERENCES decision_evidence_event(id) ON DELETE RESTRICT,
    prior_odds NUMERIC(20,10) NOT NULL CHECK (prior_odds > 0),
    likelihood_ratio NUMERIC(20,10) NOT NULL CHECK (likelihood_ratio > 0),
    posterior_odds NUMERIC(20,10) NOT NULL CHECK (posterior_odds > 0),
    posterior_probability NUMERIC(12,10) NOT NULL CHECK (posterior_probability > 0 AND posterior_probability < 1),
    effective_evidence_count NUMERIC(12,4) NOT NULL DEFAULT 1,
    calculation_version VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (hypothesis_id, evidence_event_id)
);

CREATE INDEX IF NOT EXISTS idx_decision_hypothesis_subject ON decision_hypothesis(subject_type, subject_id, status);
CREATE INDEX IF NOT EXISTS idx_decision_evidence_hypothesis ON decision_evidence_event(hypothesis_id, observed_at, created_at);
CREATE INDEX IF NOT EXISTS idx_decision_evidence_dependence ON decision_evidence_event(hypothesis_id, dependence_group);
CREATE INDEX IF NOT EXISTS idx_decision_posterior_hypothesis ON decision_posterior_update(hypothesis_id, created_at DESC);

COMMENT ON TABLE decision_hypothesis IS 'Binary hypothesis and alternative used for sequential evidence accumulation';
COMMENT ON TABLE decision_evidence_event IS 'Immutable, provenance-aware evidence event with optional likelihood inputs';
COMMENT ON TABLE decision_posterior_update IS 'Auditable posterior odds update after each evidence event';
