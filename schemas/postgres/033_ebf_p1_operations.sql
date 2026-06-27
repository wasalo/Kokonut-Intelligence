-- ============================================================
-- 033_ebf_p1_operations.sql — EBF P1 calibration and provenance
-- ============================================================

CREATE TABLE IF NOT EXISTS ebf_farm_metric_profile (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE CASCADE,
    pillar_id UUID NOT NULL REFERENCES ebf_pillar(id) ON DELETE RESTRICT,
    pillar_key VARCHAR(50) NOT NULL REFERENCES ebf_pillar(pillar_key) ON DELETE RESTRICT,
    metric_id UUID NOT NULL REFERENCES metric_definition(id) ON DELETE RESTRICT,
    metric_key VARCHAR(100) NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    rationale TEXT,
    data_source VARCHAR(255),
    collection_method VARCHAR(255),
    frequency VARCHAR(50),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebf_metric_profile_location ON ebf_farm_metric_profile(location_id);
CREATE INDEX IF NOT EXISTS idx_ebf_metric_profile_farm ON ebf_farm_metric_profile(farm_id);
CREATE INDEX IF NOT EXISTS idx_ebf_metric_profile_pillar ON ebf_farm_metric_profile(pillar_id);
CREATE INDEX IF NOT EXISTS idx_ebf_metric_profile_status ON ebf_farm_metric_profile(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ebf_metric_profile_unique
    ON ebf_farm_metric_profile(COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(farm_id, '00000000-0000-0000-0000-000000000000'::uuid), pillar_id, metric_id);

ALTER TABLE ebf_farm_metric_profile DROP CONSTRAINT IF EXISTS chk_ebf_metric_profile_status;
ALTER TABLE ebf_farm_metric_profile ADD CONSTRAINT chk_ebf_metric_profile_status CHECK (status IN ('active', 'deprecated', 'rejected'));

CREATE TABLE IF NOT EXISTS ebf_calibration_session (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_name VARCHAR(200) NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    session_date DATE NOT NULL,
    period_start DATE,
    period_end DATE,
    rubric_version VARCHAR(50) NOT NULL,
    calibration_frequency VARCHAR(50) DEFAULT 'annual',
    calibration_method VARCHAR(50) DEFAULT 'third_party',
    status VARCHAR(50) DEFAULT 'draft',
    participants JSONB DEFAULT '[]',
    calibration_notes TEXT,
    decisions JSONB DEFAULT '[]',
    report_url TEXT,
    report_hash VARCHAR(64),
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebf_calibration_session_location ON ebf_calibration_session(location_id);
CREATE INDEX IF NOT EXISTS idx_ebf_calibration_session_status ON ebf_calibration_session(status);
CREATE INDEX IF NOT EXISTS idx_ebf_calibration_session_date ON ebf_calibration_session(session_date);
CREATE INDEX IF NOT EXISTS idx_ebf_calibration_session_rubric ON ebf_calibration_session(rubric_version);

ALTER TABLE ebf_calibration_session DROP CONSTRAINT IF EXISTS chk_ebf_calibration_session_lifecycle;
ALTER TABLE ebf_calibration_session ADD CONSTRAINT chk_ebf_calibration_session_lifecycle CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE ebf_calibration_session DROP CONSTRAINT IF EXISTS chk_ebf_calibration_session_frequency;
ALTER TABLE ebf_calibration_session ADD CONSTRAINT chk_ebf_calibration_session_frequency CHECK (calibration_frequency IN ('annual', 'semi_annual', 'quarterly', 'custom'));

ALTER TABLE ebf_calibration_session DROP CONSTRAINT IF EXISTS chk_ebf_calibration_session_method;
ALTER TABLE ebf_calibration_session ADD CONSTRAINT chk_ebf_calibration_session_method CHECK (calibration_method IN ('third_party', 'team_with_report', 'mixed_panel'));

ALTER TABLE ebf_calibration_session DROP CONSTRAINT IF EXISTS chk_ebf_calibration_session_report;
ALTER TABLE ebf_calibration_session ADD CONSTRAINT chk_ebf_calibration_session_report CHECK (
    status NOT IN ('verified', 'published')
    OR calibration_method = 'third_party'
    OR NULLIF(TRIM(COALESCE(report_url, '')), '') IS NOT NULL
    OR NULLIF(TRIM(COALESCE(report_hash, '')), '') IS NOT NULL
);

CREATE TABLE IF NOT EXISTS ebf_calibration_decision (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES ebf_calibration_session(id) ON DELETE CASCADE,
    scorecard_id UUID REFERENCES ebf_scorecard(id) ON DELETE CASCADE,
    score_id UUID REFERENCES ebf_score(id) ON DELETE CASCADE,
    pillar_id UUID REFERENCES ebf_pillar(id) ON DELETE RESTRICT,
    previous_score NUMERIC(3,1) CHECK (previous_score IS NULL OR (previous_score >= 0 AND previous_score <= 10)),
    adjusted_score NUMERIC(3,1) CHECK (adjusted_score IS NULL OR (adjusted_score >= 0 AND adjusted_score <= 10)),
    reason TEXT NOT NULL,
    evidence_reference TEXT,
    decision_status VARCHAR(50) DEFAULT 'draft',
    decided_by UUID,
    decided_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ebf_calibration_decision_session ON ebf_calibration_decision(session_id);
CREATE INDEX IF NOT EXISTS idx_ebf_calibration_decision_scorecard ON ebf_calibration_decision(scorecard_id);
CREATE INDEX IF NOT EXISTS idx_ebf_calibration_decision_score ON ebf_calibration_decision(score_id);

ALTER TABLE ebf_calibration_decision DROP CONSTRAINT IF EXISTS chk_ebf_calibration_decision_status;
ALTER TABLE ebf_calibration_decision ADD CONSTRAINT chk_ebf_calibration_decision_status CHECK (decision_status IN ('draft', 'submitted', 'verified', 'rejected'));

CREATE TABLE IF NOT EXISTS ebf_trust_graph_node (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_type VARCHAR(50) NOT NULL,
    reference_id UUID NOT NULL,
    reference_type VARCHAR(100) NOT NULL,
    label VARCHAR(200),
    public_safe BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(node_type, reference_type, reference_id)
);

CREATE INDEX IF NOT EXISTS idx_ebf_trust_node_type ON ebf_trust_graph_node(node_type);
CREATE INDEX IF NOT EXISTS idx_ebf_trust_node_reference ON ebf_trust_graph_node(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_ebf_trust_node_public ON ebf_trust_graph_node(public_safe);

ALTER TABLE ebf_trust_graph_node DROP CONSTRAINT IF EXISTS chk_ebf_trust_node_type;
ALTER TABLE ebf_trust_graph_node ADD CONSTRAINT chk_ebf_trust_node_type CHECK (node_type IN (
    'farm', 'location', 'operator', 'pillar', 'metric', 'scorecard', 'score', 'evidence',
    'data_source', 'measurement_method', 'reviewer', 'calibration_session', 'calibration_decision',
    'attestation', 'report_snapshot', 'dashboard_output', 'improvement_recommendation'
));

CREATE TABLE IF NOT EXISTS ebf_trust_graph_edge (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_node_id UUID NOT NULL REFERENCES ebf_trust_graph_node(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES ebf_trust_graph_node(id) ON DELETE CASCADE,
    edge_type VARCHAR(50) NOT NULL,
    public_safe BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_node_id, target_node_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_ebf_trust_edge_source ON ebf_trust_graph_edge(source_node_id);
CREATE INDEX IF NOT EXISTS idx_ebf_trust_edge_target ON ebf_trust_graph_edge(target_node_id);
CREATE INDEX IF NOT EXISTS idx_ebf_trust_edge_type ON ebf_trust_graph_edge(edge_type);
CREATE INDEX IF NOT EXISTS idx_ebf_trust_edge_public ON ebf_trust_graph_edge(public_safe);

ALTER TABLE ebf_trust_graph_edge DROP CONSTRAINT IF EXISTS chk_ebf_trust_edge_type;
ALTER TABLE ebf_trust_graph_edge ADD CONSTRAINT chk_ebf_trust_edge_type CHECK (edge_type IN (
    'produced', 'supports', 'reviewed_by', 'measured_by', 'calibrated_by', 'attested_by',
    'published_in', 'derived_from', 'requires', 'summarized_by', 'recommended_for'
));

CREATE TABLE IF NOT EXISTS ebf_improvement_recommendation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    score_id UUID NOT NULL REFERENCES ebf_score(id) ON DELETE CASCADE,
    pillar_id UUID NOT NULL REFERENCES ebf_pillar(id) ON DELETE RESTRICT,
    recommendation_text TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium',
    estimated_impact TEXT,
    resource_requirements TEXT,
    status VARCHAR(50) DEFAULT 'open',
    assigned_to UUID,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebf_recommendation_score ON ebf_improvement_recommendation(score_id);
CREATE INDEX IF NOT EXISTS idx_ebf_recommendation_pillar ON ebf_improvement_recommendation(pillar_id);
CREATE INDEX IF NOT EXISTS idx_ebf_recommendation_status ON ebf_improvement_recommendation(status);
CREATE INDEX IF NOT EXISTS idx_ebf_recommendation_priority ON ebf_improvement_recommendation(priority);

ALTER TABLE ebf_improvement_recommendation DROP CONSTRAINT IF EXISTS chk_ebf_recommendation_priority;
ALTER TABLE ebf_improvement_recommendation ADD CONSTRAINT chk_ebf_recommendation_priority CHECK (priority IN ('high', 'medium', 'low'));

ALTER TABLE ebf_improvement_recommendation DROP CONSTRAINT IF EXISTS chk_ebf_recommendation_status;
ALTER TABLE ebf_improvement_recommendation ADD CONSTRAINT chk_ebf_recommendation_status CHECK (status IN ('open', 'in_progress', 'completed', 'deferred', 'rejected'));

ALTER TABLE ebf_scorecard ADD COLUMN IF NOT EXISTS calibration_session_id UUID REFERENCES ebf_calibration_session(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_ebf_scorecard_calibration ON ebf_scorecard(calibration_session_id);

CREATE OR REPLACE VIEW v_ebf_evidence_gap_summary AS
SELECT
    esc.id AS scorecard_id,
    esc.location_id,
    l.name AS location_name,
    ep.pillar_key,
    ep.pillar_name,
    es.normalized_score,
    es.confidence_level,
    es.evidence_maturity_level,
    em.label AS evidence_maturity_label,
    COUNT(ese.id) AS evidence_count,
    COUNT(ese.id) FILTER (WHERE ese.evidence_maturity_level >= 4) AS public_safe_evidence_count,
    MIN(ese.evidence_maturity_level) AS min_linked_evidence_maturity,
    MAX(ese.evidence_maturity_level) AS max_linked_evidence_maturity,
    CASE
        WHEN COUNT(ese.id) = 0 THEN 'missing_evidence'
        WHEN es.evidence_maturity_level < 4 THEN 'below_public_threshold'
        WHEN ep.pillar_key = 'carbon_sequestration' AND es.evidence_maturity_level < 6 THEN 'carbon_requires_level6'
        WHEN es.confidence_level IN ('low', 'insufficient_evidence') THEN 'low_confidence'
        ELSE 'ready_for_review'
    END AS gap_status
FROM ebf_score es
JOIN ebf_scorecard esc ON esc.id = es.scorecard_id
JOIN location l ON l.id = esc.location_id
JOIN ebf_pillar ep ON ep.id = es.pillar_id
LEFT JOIN ebf_score_evidence ese ON ese.score_id = es.id
LEFT JOIN evidence_maturity_level em ON em.level = es.evidence_maturity_level
WHERE esc.status != 'rejected'
GROUP BY esc.id, esc.location_id, l.name, ep.pillar_key, ep.pillar_name, ep.sort_order,
         es.normalized_score, es.confidence_level, es.evidence_maturity_level, em.label
ORDER BY l.name, esc.period_end DESC, ep.sort_order;

CREATE OR REPLACE VIEW v_ebf_calibration_history AS
SELECT
    ecs.id AS session_id,
    ecs.session_name,
    ecs.location_id,
    l.name AS location_name,
    ecs.session_date,
    ecs.rubric_version,
    ecs.calibration_frequency,
    ecs.calibration_method,
    ecs.status,
    COUNT(ecd.id) AS decision_count,
    COUNT(ecd.id) FILTER (WHERE ecd.decision_status = 'verified') AS verified_decision_count,
    ecs.report_url,
    ecs.report_hash
FROM ebf_calibration_session ecs
LEFT JOIN location l ON l.id = ecs.location_id
LEFT JOIN ebf_calibration_decision ecd ON ecd.session_id = ecs.id
WHERE ecs.status != 'rejected'
GROUP BY ecs.id, ecs.session_name, ecs.location_id, l.name, ecs.session_date, ecs.rubric_version,
         ecs.calibration_frequency, ecs.calibration_method, ecs.status, ecs.report_url, ecs.report_hash
ORDER BY ecs.session_date DESC, ecs.created_at DESC;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('ebf-p1-operations-v1', 'EBF P1 calibration, trust graph, farm-specific metrics, recommendations, and evidence gap views', 'schema 033')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
