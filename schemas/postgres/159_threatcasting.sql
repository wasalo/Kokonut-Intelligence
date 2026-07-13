-- 159_threatcasting.sql
-- Threatcasting framework: cross-impact analysis, warning flags, threat intelligence,
-- narrative construction, backcasting, multi-horizon planning, desirability assessment.

BEGIN;

-- ---------------------------------------------------------------------------
-- Core threat catalog
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id),
    threat_name VARCHAR(200) NOT NULL,
    threat_type VARCHAR(50) NOT NULL
        CHECK (threat_type IN ('climate','policy','market','technology','ecological','social','health','security')),
    description TEXT,
    severity_potential VARCHAR(20) NOT NULL
        CHECK (severity_potential IN ('low','medium','high','critical')),
    probability DECIMAL(5,4) CHECK (probability >= 0 AND probability <= 1),
    velocity VARCHAR(20) NOT NULL
        CHECK (velocity IN ('slow','moderate','fast','rapid')),
    reversibility VARCHAR(20) NOT NULL
        CHECK (reversibility IN ('reversible','partially','irreversible')),
    time_horizon_years INT DEFAULT 5,
    is_active BOOLEAN DEFAULT TRUE,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_threat_location ON threat(location_id);
CREATE INDEX IF NOT EXISTS idx_threat_type ON threat(threat_type);
CREATE INDEX IF NOT EXISTS idx_threat_active ON threat(is_active);

-- ---------------------------------------------------------------------------
-- Warning flags (observable indicators)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_flag (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    threat_id UUID NOT NULL REFERENCES threat(id) ON DELETE CASCADE,
    flag_name VARCHAR(200) NOT NULL,
    description TEXT,
    indicator_type VARCHAR(50) NOT NULL
        CHECK (indicator_type IN ('quantitative','qualitative','threshold','pattern','manual')),
    current_value TEXT,
    previous_value TEXT,
    threshold_critical DECIMAL(10,4),
    threshold_warning DECIMAL(10,4),
    threshold_normal DECIMAL(10,4),
    comparison_operator VARCHAR(10) DEFAULT 'gte'
        CHECK (comparison_operator IN ('gt','gte','lt','lte','eq','neq','between')),
    unit VARCHAR(50),
    status VARCHAR(20) DEFAULT 'normal'
        CHECK (status IN ('normal','elevated','warning','critical','unknown')),
    data_source VARCHAR(100),
    check_frequency_hours INT DEFAULT 24,
    last_checked_at TIMESTAMPTZ,
    last_value_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_threat_flag_threat ON threat_flag(threat_id);
CREATE INDEX IF NOT EXISTS idx_threat_flag_status ON threat_flag(status);

-- ---------------------------------------------------------------------------
-- Cross-impact matrix
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_cross_impact (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_threat_id UUID NOT NULL REFERENCES threat(id) ON DELETE CASCADE,
    target_threat_id UUID NOT NULL REFERENCES threat(id) ON DELETE CASCADE,
    impact_type VARCHAR(20) NOT NULL
        CHECK (impact_type IN ('amplifies','attenuates','triggers','delays','redirects','enables')),
    impact_magnitude DECIMAL(5,4) NOT NULL CHECK (impact_magnitude >= 0 AND impact_magnitude <= 1),
    impact_direction VARCHAR(10) NOT NULL CHECK (impact_direction IN ('positive','negative')),
    description TEXT,
    confidence_level VARCHAR(20) DEFAULT 'medium'
        CHECK (confidence_level IN ('low','medium','high')),
    evidence_source TEXT,
    lag_days INT DEFAULT 0,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_threat_id, target_threat_id)
);

CREATE INDEX IF NOT EXISTS idx_cross_impact_source ON threat_cross_impact(source_threat_id);
CREATE INDEX IF NOT EXISTS idx_cross_impact_target ON threat_cross_impact(target_threat_id);

-- ---------------------------------------------------------------------------
-- External signals (aggregated from various sources)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_signal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    threat_id UUID REFERENCES threat(id) ON DELETE SET NULL,
    signal_source VARCHAR(100) NOT NULL,
    source_reference TEXT,
    signal_type VARCHAR(50) NOT NULL
        CHECK (signal_type IN ('text','numeric','categorical','event','alert')),
    content TEXT NOT NULL,
    structured_data JSONB DEFAULT '{}',
    confidence DECIMAL(5,4) CHECK (confidence >= 0 AND confidence <= 1),
    relevance_score DECIMAL(5,4) CHECK (relevance_score >= 0 AND relevance_score <= 1),
    sentiment DECIMAL(3,2) CHECK (sentiment >= -1 AND sentiment <= 1),
    signal_date TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    classified BOOLEAN DEFAULT FALSE,
    classification_notes TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_signal_threat ON threat_signal(threat_id);
CREATE INDEX IF NOT EXISTS idx_signal_date ON threat_signal(signal_date);
CREATE INDEX IF NOT EXISTS idx_signal_source ON threat_signal(signal_source);
CREATE INDEX IF NOT EXISTS idx_signal_unclassified ON threat_signal(classified) WHERE classified = FALSE;

-- ---------------------------------------------------------------------------
-- Threat narratives (detailed scenario stories)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_narrative (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    threat_id UUID NOT NULL REFERENCES threat(id) ON DELETE CASCADE,
    narrative_type VARCHAR(20) NOT NULL
        CHECK (narrative_type IN ('desirable','undesirable','baseline','wildcard')),
    title VARCHAR(200) NOT NULL,
    summary TEXT NOT NULL,
    detailed_story TEXT NOT NULL,
    timeline_years INT NOT NULL,
    probability_estimate DECIMAL(5,4) CHECK (probability_estimate >= 0 AND probability_estimate <= 1),
    desirability_score DECIMAL(5,4) CHECK (desirability_score >= -1 AND desirability_score <= 1),
    impact_severity VARCHAR(20) CHECK (impact_severity IN ('low','medium','high','critical')),
    key_indicators TEXT[] DEFAULT '{}',
    cascading_effects UUID[] DEFAULT '{}',
    recommended_preparedness TEXT,
    recommended_response TEXT,
    is_primary BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_narrative_threat ON threat_narrative(threat_id);
CREATE INDEX IF NOT EXISTS idx_narrative_type ON threat_narrative(narrative_type);

-- ---------------------------------------------------------------------------
-- Multi-horizon planning
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_horizon (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id),
    horizon_name VARCHAR(100) NOT NULL,
    horizon_years INT NOT NULL CHECK (horizon_years > 0),
    description TEXT,
    focus_areas TEXT[] DEFAULT '{}',
    desirability_framework VARCHAR(50) DEFAULT 'gnh_aligned'
        CHECK (desirability_framework IN ('gnh_aligned','wellbeing','economic','composite','custom')),
    review_frequency_months INT DEFAULT 12,
    last_reviewed_at TIMESTAMPTZ,
    next_review_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_horizon_location ON threat_horizon(location_id);

-- ---------------------------------------------------------------------------
-- Horizon ↔ threat junction
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_horizon_threat (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    horizon_id UUID NOT NULL REFERENCES threat_horizon(id) ON DELETE CASCADE,
    threat_id UUID NOT NULL REFERENCES threat(id) ON DELETE CASCADE,
    relevance_score DECIMAL(5,4) CHECK (relevance_score >= 0 AND relevance_score <= 1),
    time_to_impact_years DECIMAL(4,1),
    priority_rank INT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(horizon_id, threat_id)
);

CREATE INDEX IF NOT EXISTS idx_horizon_threat_horizon ON threat_horizon_threat(horizon_id);
CREATE INDEX IF NOT EXISTS idx_horizon_threat_threat ON threat_horizon_threat(threat_id);

-- ---------------------------------------------------------------------------
-- Desirability assessment (tied to wellbeing / GNH)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_desirability_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    narrative_id UUID NOT NULL REFERENCES threat_narrative(id) ON DELETE CASCADE,
    assessment_framework VARCHAR(50) NOT NULL
        CHECK (assessment_framework IN ('gnh','8_forms_capital','sdg','wellbeing','composite','custom')),
    dimension VARCHAR(100) NOT NULL,
    score DECIMAL(5,4) NOT NULL CHECK (score >= -1 AND score <= 1),
    weight DECIMAL(5,4) DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 1),
    rationale TEXT,
    data_sources TEXT[] DEFAULT '{}',
    assessed_by VARCHAR(100),
    assessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_desirability_narrative ON threat_desirability_assessment(narrative_id);
CREATE INDEX IF NOT EXISTS idx_desirability_framework ON threat_desirability_assessment(assessment_framework);

-- ---------------------------------------------------------------------------
-- Backcasting plans (working backward from future state)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_backcast_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    narrative_id UUID NOT NULL REFERENCES threat_narrative(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id),
    plan_name VARCHAR(200) NOT NULL,
    future_state_description TEXT NOT NULL,
    current_gap_analysis TEXT NOT NULL,
    milestone_order INT NOT NULL,
    milestone_description TEXT NOT NULL,
    milestone_target_date DATE,
    milestone_status VARCHAR(20) DEFAULT 'pending'
        CHECK (milestone_status IN ('pending','in_progress','completed','skipped','blocked')),
    dependencies UUID[] DEFAULT '{}',
    responsible_party VARCHAR(100),
    resource_requirements TEXT,
    completion_evidence TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backcast_narrative ON threat_backcast_plan(narrative_id);
CREATE INDEX IF NOT EXISTS idx_backcast_location ON threat_backcast_plan(location_id);

-- ---------------------------------------------------------------------------
-- Cascading failure scenarios
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_cascade (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_threat_id UUID NOT NULL REFERENCES threat(id) ON DELETE CASCADE,
    cascade_name VARCHAR(200) NOT NULL,
    description TEXT,
    failure_chain UUID[] NOT NULL,
    cascade_probability DECIMAL(5,4) CHECK (cascade_probability >= 0 AND cascade_probability <= 1),
    total_impact_severity VARCHAR(20) CHECK (total_impact_severity IN ('low','medium','high','critical')),
    time_to_cascade_hours INT,
    mitigation_strategies TEXT[] DEFAULT '{}',
    early_warning_signals TEXT[] DEFAULT '{}',
    is_enabled BOOLEAN DEFAULT TRUE,
    last_evaluated_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cascade_trigger ON threat_cascade(trigger_threat_id);

-- ---------------------------------------------------------------------------
-- Public views
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_public_threat_summary AS
SELECT
    t.id AS threat_id,
    t.location_id,
    l.name AS location_name,
    t.threat_name,
    t.threat_type,
    t.severity_potential,
    t.probability,
    t.velocity,
    t.reversibility,
    t.time_horizon_years,
    t.is_active,
    t.created_at
FROM threat t
LEFT JOIN location l ON l.id = t.location_id
WHERE t.is_active = TRUE;

CREATE OR REPLACE VIEW v_public_threat_flag_status AS
SELECT
    f.id AS flag_id,
    f.threat_id,
    t.threat_name,
    t.threat_type,
    f.flag_name,
    f.indicator_type,
    f.current_value,
    f.status,
    f.data_source,
    f.last_checked_at,
    f.last_value_at
FROM threat_flag f
JOIN threat t ON t.id = f.threat_id
WHERE f.is_active = TRUE;

CREATE OR REPLACE VIEW v_public_cross_impact_summary AS
SELECT
    ci.id AS impact_id,
    ci.source_threat_id,
    ts.threat_name AS source_threat_name,
    ci.target_threat_id,
    tt.threat_name AS target_threat_name,
    ci.impact_type,
    ci.impact_magnitude,
    ci.impact_direction,
    ci.confidence_level,
    ci.lag_days
FROM threat_cross_impact ci
JOIN threat ts ON ts.id = ci.source_threat_id
JOIN threat tt ON tt.id = ci.target_threat_id
WHERE ci.is_enabled = TRUE;

CREATE OR REPLACE VIEW v_public_narrative_summary AS
SELECT
    n.id AS narrative_id,
    n.threat_id,
    t.threat_name,
    n.narrative_type,
    n.title,
    n.summary,
    n.timeline_years,
    n.probability_estimate,
    n.desirability_score,
    n.impact_severity,
    n.is_primary
FROM threat_narrative n
JOIN threat t ON t.id = n.threat_id;

CREATE OR REPLACE VIEW v_public_horizon_overview AS
SELECT
    h.id AS horizon_id,
    h.location_id,
    l.name AS location_name,
    h.horizon_name,
    h.horizon_years,
    h.focus_areas,
    h.desirability_framework,
    h.last_reviewed_at,
    h.next_review_at,
    h.is_active,
    (SELECT COUNT(*) FROM threat_horizon_threat ht WHERE ht.horizon_id = h.id) AS linked_threat_count
FROM threat_horizon h
LEFT JOIN location l ON l.id = h.location_id
WHERE h.is_active = TRUE;

CREATE OR REPLACE VIEW v_public_cascade_overview AS
SELECT
    c.id AS cascade_id,
    c.cascade_name,
    c.trigger_threat_id,
    t.threat_name AS trigger_threat_name,
    array_length(c.failure_chain, 1) AS chain_length,
    c.cascade_probability,
    c.total_impact_severity,
    c.time_to_cascade_hours,
    c.mitigation_strategies,
    c.is_enabled,
    c.last_evaluated_at
FROM threat_cascade c
JOIN threat t ON t.id = c.trigger_threat_id
WHERE c.is_enabled = TRUE;

COMMIT;
