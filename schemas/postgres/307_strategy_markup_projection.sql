-- ============================================================
-- 307_strategy_markup_projection.sql
-- StratML-compatible strategy relationships, performance, and imports.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_relationship (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    subject_type VARCHAR(40) NOT NULL,
    subject_id UUID NOT NULL,
    relationship_type VARCHAR(30) NOT NULL CHECK (relationship_type IN (
        'supports', 'enables', 'depends_on', 'causes', 'contributes_to',
        'measured_by', 'implemented_by', 'funded_by', 'affects_stakeholder'
    )),
    object_type VARCHAR(40) NOT NULL,
    object_id UUID NOT NULL,
    rationale TEXT,
    evidence_link_id UUID REFERENCES strategy_evidence_link(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (strategy_plan_id, subject_type, subject_id, relationship_type, object_type, object_id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_relationship_subject
    ON strategy_relationship(strategy_plan_id, subject_type, subject_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_relationship_object
    ON strategy_relationship(strategy_plan_id, object_type, object_id, status);

CREATE TABLE IF NOT EXISTS strategy_performance_indicator (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    strategy_map_id UUID REFERENCES strategy_map(id) ON DELETE SET NULL,
    objective_id UUID REFERENCES objective(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metric_key VARCHAR(120),
    baseline_value NUMERIC,
    target_value NUMERIC,
    actual_value NUMERIC,
    period_start DATE,
    period_end DATE,
    direction VARCHAR(20) NOT NULL DEFAULT 'gte'
        CHECK (direction IN ('gte', 'lte', 'range')),
    unit VARCHAR(80),
    calculation_method TEXT,
    data_source_type VARCHAR(60),
    data_source_id UUID,
    data_source_ref TEXT,
    evidence_maturity INTEGER REFERENCES evidence_maturity_level(level),
    stakeholder_impact TEXT,
    variance_value NUMERIC,
    variance_pct NUMERIC,
    variance_explanation TEXT,
    review_status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_indicator_plan
    ON strategy_performance_indicator(strategy_plan_id, review_status, period_end);
CREATE INDEX IF NOT EXISTS idx_strategy_indicator_objective
    ON strategy_performance_indicator(objective_id, metric_key);

CREATE TABLE IF NOT EXISTS strategy_value_chain_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    performance_indicator_id UUID REFERENCES strategy_performance_indicator(id) ON DELETE CASCADE,
    value_chain_type VARCHAR(30) NOT NULL CHECK (value_chain_type IN (
        'input', 'process', 'output', 'outcome', 'stakeholder_result'
    )),
    record_type VARCHAR(60),
    record_id UUID,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sequence_order INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    evidence_link_id UUID REFERENCES strategy_evidence_link(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_value_chain_indicator
    ON strategy_value_chain_link(performance_indicator_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_strategy_value_chain_plan
    ON strategy_value_chain_link(strategy_plan_id, value_chain_type, status);

CREATE TABLE IF NOT EXISTS strategy_markup_document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID REFERENCES strategy_plan(id) ON DELETE SET NULL,
    source_url TEXT,
    source_cid VARCHAR(255),
    content_hash VARCHAR(128) NOT NULL,
    media_type VARCHAR(100) NOT NULL DEFAULT 'application/xml',
    document_name VARCHAR(255),
    parsed_projection JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    imported_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (content_hash)
);

CREATE INDEX IF NOT EXISTS idx_strategy_markup_document_search
    ON strategy_markup_document(status, strategy_plan_id, imported_at DESC);

COMMENT ON TABLE strategy_relationship IS 'Typed, governed links between strategic intentions and execution/evidence records';
COMMENT ON TABLE strategy_performance_indicator IS 'Unified StratML-compatible target and actual performance indicators';
COMMENT ON TABLE strategy_value_chain_link IS 'Links indicators to inputs, processes, outputs, outcomes, and stakeholder results';
COMMENT ON TABLE strategy_markup_document IS 'Hash and metadata registry for imported StratML documents; raw content remains external';
