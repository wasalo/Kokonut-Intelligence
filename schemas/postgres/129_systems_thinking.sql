-- ============================================================
-- 129_systems_thinking.sql — Causal loops, leverage, archetypes
-- ============================================================

CREATE TABLE IF NOT EXISTS causal_loop (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loop_name VARCHAR(100) NOT NULL UNIQUE,
    loop_type VARCHAR(30) NOT NULL
        CHECK (loop_type IN ('reinforcing', 'balancing', 'archetype')),
    archetype VARCHAR(100),
    description TEXT NOT NULL,
    domain VARCHAR(50) NOT NULL DEFAULT 'farm'
        CHECK (domain IN ('farm', 'ecological', 'financial', 'social', 'governance')),
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_causal_loop_type ON causal_loop (loop_type);
CREATE INDEX IF NOT EXISTS idx_causal_loop_domain ON causal_loop (domain);

CREATE TABLE IF NOT EXISTS causal_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loop_id UUID NOT NULL REFERENCES causal_loop(id) ON DELETE CASCADE,
    source_variable VARCHAR(100) NOT NULL,
    target_variable VARCHAR(100) NOT NULL,
    polarity VARCHAR(2) NOT NULL CHECK (polarity IN ('+', '-')),
    strength DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    description TEXT,
    delay_hours INTEGER DEFAULT 0,
    data_source VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_causal_link_loop ON causal_link (loop_id);
CREATE INDEX IF NOT EXISTS idx_causal_link_source ON causal_link (source_variable);

CREATE TABLE IF NOT EXISTS system_variable (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variable_name VARCHAR(100) NOT NULL UNIQUE,
    variable_type VARCHAR(20) NOT NULL
        CHECK (variable_type IN ('stock', 'flow', 'auxiliary', 'constant')),
    unit VARCHAR(50),
    current_value DOUBLE PRECISION DEFAULT 0.0,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    location_id UUID,
    source_table VARCHAR(100),
    source_column VARCHAR(100),
    last_observed_at TIMESTAMPTZ,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_variable_type ON system_variable (variable_type);
CREATE INDEX IF NOT EXISTS idx_system_variable_location ON system_variable (location_id);

CREATE TABLE IF NOT EXISTS stock_flow_model (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    equations JSONB NOT NULL DEFAULT '{}',
    initial_conditions JSONB NOT NULL DEFAULT '{}',
    parameters JSONB NOT NULL DEFAULT '{}',
    time_unit VARCHAR(20) NOT NULL DEFAULT 'day',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stock_flow_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES stock_flow_model(id) ON DELETE CASCADE,
    location_id UUID NOT NULL,
    scenario_name VARCHAR(100) NOT NULL DEFAULT 'baseline',
    parameters JSONB NOT NULL DEFAULT '{}',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    time_step_days INTEGER NOT NULL DEFAULT 1,
    results JSONB NOT NULL DEFAULT '{}',
    trajectory JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'completed'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    error_message TEXT,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_by VARCHAR(100) NOT NULL DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_stock_flow_run_model ON stock_flow_run (model_id, location_id);
CREATE INDEX IF NOT EXISTS idx_stock_flow_run_status ON stock_flow_run (status);

CREATE TABLE IF NOT EXISTS system_archetype (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archetype_name VARCHAR(100) NOT NULL,
    location_id UUID NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    evidence JSONB NOT NULL DEFAULT '{}',
    active_variables JSONB NOT NULL DEFAULT '[]',
    suggested_intervention TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'resolved', 'dismissed')),
    resolved_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_archetype_location ON system_archetype (location_id, status);
CREATE INDEX IF NOT EXISTS idx_system_archetype_name ON system_archetype (archetype_name);

CREATE TABLE IF NOT EXISTS leverage_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL,
    leverage_point INTEGER NOT NULL CHECK (leverage_point BETWEEN 1 AND 12),
    point_name VARCHAR(100) NOT NULL,
    current_state TEXT,
    impact_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    intervention_suggestion TEXT,
    data_sources JSONB NOT NULL DEFAULT '[]',
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assessed_by VARCHAR(100) NOT NULL DEFAULT 'system',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leverage_assessment_location ON leverage_assessment (location_id, impact_score DESC);
CREATE INDEX IF NOT EXISTS idx_leverage_assessment_point ON leverage_assessment (leverage_point);

CREATE TABLE IF NOT EXISTS time_delay (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type VARCHAR(100) NOT NULL,
    effect_type VARCHAR(100) NOT NULL,
    expected_delay_hours INTEGER NOT NULL,
    min_delay_hours INTEGER,
    max_delay_hours INTEGER,
    domain VARCHAR(50) NOT NULL DEFAULT 'farm',
    description TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_time_delay_action_effect ON time_delay (action_type, effect_type);

CREATE TABLE IF NOT EXISTS mental_model (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stakeholder_id UUID NOT NULL,
    stakeholder_type VARCHAR(50) NOT NULL DEFAULT 'farmer',
    worldview_dimension VARCHAR(100) NOT NULL,
    position DOUBLE PRECISION NOT NULL DEFAULT 0.5
        CHECK (position BETWEEN 0.0 AND 1.0),
    position_label VARCHAR(100),
    rationale TEXT,
    evidence JSONB NOT NULL DEFAULT '{}',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    captured_by VARCHAR(100) NOT NULL DEFAULT 'system',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mental_model_stakeholder ON mental_model (stakeholder_id);
CREATE INDEX IF NOT EXISTS idx_mental_model_dimension ON mental_model (worldview_dimension);

CREATE TABLE IF NOT EXISTS structural_assumption (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assumption_text TEXT NOT NULL,
    location_id UUID,
    domain VARCHAR(50) NOT NULL DEFAULT 'farm',
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'challenged', 'validated', 'deprecated')),
    challenge_evidence TEXT,
    challenged_at TIMESTAMPTZ,
    challenged_by VARCHAR(100),
    original_source VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_structural_assumption_location ON structural_assumption (location_id, status);
CREATE INDEX IF NOT EXISTS idx_structural_assumption_status ON structural_assumption (status);
