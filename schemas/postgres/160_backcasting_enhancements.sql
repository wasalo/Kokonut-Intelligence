-- 160_backcasting_enhancements.sql
-- Backcasting improvements: sustainability principles, milestone alignment,
-- assumption challenges, and path comparison.

-- 1. backcast_principle — sustainability principles that define success
CREATE TABLE IF NOT EXISTS backcast_principle (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    narrative_id UUID NOT NULL REFERENCES threat_narrative(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id),
    principle_name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    principle_type VARCHAR(50) NOT NULL
        CHECK (principle_type IN ('sustainability','operational','financial','ecological','social','custom')),
    metric_key VARCHAR(100) REFERENCES metric_definition(metric_key),
    comparison_operator VARCHAR(10) DEFAULT 'gte'
        CHECK (comparison_operator IN ('gt','gte','lt','lte','eq','neq','between')),
    target_value NUMERIC(15,4),
    target_value_upper NUMERIC(15,4),
    invert_direction BOOLEAN DEFAULT FALSE,
    weight DECIMAL(5,4) DEFAULT 1.0,
    source_system VARCHAR(50) DEFAULT 'manual'
        CHECK (source_system IN ('metric','crisp','manual')),
    crisp_dimension VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. backcast_principle_alignment — milestone ↔ principle alignment scores
CREATE TABLE IF NOT EXISTS backcast_principle_alignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    milestone_id UUID NOT NULL REFERENCES threat_backcast_plan(id) ON DELETE CASCADE,
    principle_id UUID NOT NULL REFERENCES backcast_principle(id) ON DELETE CASCADE,
    alignment_score DECIMAL(5,4) NOT NULL CHECK (alignment_score >= -1 AND alignment_score <= 1),
    current_value NUMERIC(15,4),
    target_value NUMERIC(15,4),
    gap NUMERIC(15,4),
    alignment_evidence TEXT,
    assessed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(milestone_id, principle_id)
);

-- 3. backcast_assumption_challenge — assumption rethinking during backcasting
CREATE TABLE IF NOT EXISTS backcast_assumption_challenge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES threat_backcast_plan(id) ON DELETE CASCADE,
    narrative_id UUID NOT NULL REFERENCES threat_narrative(id),
    original_assumption TEXT NOT NULL,
    challenged_assumption TEXT NOT NULL,
    challenge_reason TEXT,
    outcome VARCHAR(20) DEFAULT 'pending'
        CHECK (outcome IN ('pending','confirmed','modified','rejected')),
    revised_milestone_id UUID REFERENCES threat_backcast_plan(id),
    impact_on_principles TEXT,
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- 4. backcast_path_comparison — compare multiple routes to same future
CREATE TABLE IF NOT EXISTS backcast_path_comparison (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id),
    comparison_name VARCHAR(200) NOT NULL,
    narrative_ids UUID[] NOT NULL,
    comparison_criteria JSONB NOT NULL DEFAULT '{}',
    auto_scores JSONB NOT NULL DEFAULT '{}',
    manual_scores JSONB NOT NULL DEFAULT '{}',
    final_scores JSONB NOT NULL DEFAULT '{}',
    winner_narrative_id UUID,
    winner_score DECIMAL(5,4),
    rationale TEXT,
    compared_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bp_narrative ON backcast_principle(narrative_id);
CREATE INDEX IF NOT EXISTS idx_bp_location ON backcast_principle(location_id);
CREATE INDEX IF NOT EXISTS idx_bp_metric_key ON backcast_principle(metric_key);
CREATE INDEX IF NOT EXISTS idx_bpa_milestone ON backcast_principle_alignment(milestone_id);
CREATE INDEX IF NOT EXISTS idx_bpa_principle ON backcast_principle_alignment(principle_id);
CREATE INDEX IF NOT EXISTS idx_bac_plan ON backcast_assumption_challenge(plan_id);
CREATE INDEX IF NOT EXISTS idx_bac_narrative ON backcast_assumption_challenge(narrative_id);
CREATE INDEX IF NOT EXISTS idx_bpc_location ON backcast_path_comparison(location_id);

-- Views
CREATE OR REPLACE VIEW v_backcast_principle_summary AS
SELECT
    bp.id AS principle_id,
    bp.narrative_id,
    bp.location_id,
    bp.principle_name,
    bp.principle_type,
    bp.metric_key,
    bp.comparison_operator,
    bp.target_value,
    bp.target_value_upper,
    bp.invert_direction,
    bp.weight,
    bp.source_system,
    bp.crisp_dimension,
    nt.title AS narrative_title,
    t.threat_name
FROM backcast_principle bp
JOIN threat_narrative nt ON nt.id = bp.narrative_id
JOIN threat t ON t.id = nt.threat_id
WHERE bp.is_active = TRUE;

CREATE OR REPLACE VIEW v_backcast_alignment_summary AS
SELECT
    pa.id AS alignment_id,
    pa.milestone_id,
    tbp.plan_name,
    tbp.milestone_description,
    tbp.milestone_status,
    pa.principle_id,
    bp.principle_name,
    bp.principle_type,
    bp.metric_key,
    pa.alignment_score,
    pa.current_value,
    pa.target_value,
    pa.gap,
    pa.assessed_at
FROM backcast_principle_alignment pa
JOIN backcast_principle bp ON bp.id = pa.principle_id
JOIN threat_backcast_plan tbp ON tbp.id = pa.milestone_id;

CREATE OR REPLACE VIEW v_backcast_path_comparison_summary AS
SELECT
    bpc.id AS comparison_id,
    bpc.location_id,
    bpc.comparison_name,
    array_length(bpc.narrative_ids, 1) AS path_count,
    bpc.winner_narrative_id,
    bpc.winner_score,
    bpc.rationale,
    bpc.compared_by,
    bpc.created_at,
    nt.title AS winner_title
FROM backcast_path_comparison bpc
LEFT JOIN threat_narrative nt ON nt.id = bpc.winner_narrative_id;
