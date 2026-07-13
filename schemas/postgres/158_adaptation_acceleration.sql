-- ============================================================
-- 158_adaptation_acceleration.sql — Adaptation Acceleration
-- ============================================================
-- Tracks whether the system is getting faster at learning over time.
-- Covers OODA velocity, feedback rates, improvement trends, ML
-- retrain scheduling, cross-domain insight transfer, growth curve
-- detection, paradigm shift detection, and meta-learning.

-- -------------------------------------------------------
-- Adaptation Velocity Log
-- -------------------------------------------------------
-- Rolling metrics: OODA cycle times, feedback rates,
-- effectiveness trends, time-to-action.

CREATE TABLE IF NOT EXISTS adaptation_velocity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,

    -- OODA velocity
    avg_cycle_time_ms NUMERIC(10,2),
    median_cycle_time_ms NUMERIC(10,2),
    cycles_completed INTEGER,
    cycle_time_trend NUMERIC(5,2),

    -- Feedback velocity
    feedback_rate NUMERIC(5,2),
    feedback_success_rate NUMERIC(5,2),
    feedback_velocity_trend NUMERIC(5,2),

    -- Effectiveness velocity
    avg_effectiveness_pct NUMERIC(5,2),
    effectiveness_trend NUMERIC(5,2),
    effectiveness_ma7 NUMERIC(5,2),
    effectiveness_ma30 NUMERIC(5,2),

    -- Time-to-action
    avg_time_to_insight_hours NUMERIC(8,2),
    avg_time_to_action_hours NUMERIC(8,2),
    time_to_action_trend NUMERIC(5,2),

    -- Acceleration classification
    velocity_status VARCHAR(20) NOT NULL DEFAULT 'insufficient_data'
        CHECK (velocity_status IN (
            'accelerating', 'stable', 'decelerating',
            'stalled', 'insufficient_data'
        )),
    acceleration_score NUMERIC(5,2),

    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_velocity_location
    ON adaptation_velocity_log (location_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_velocity_status
    ON adaptation_velocity_log (velocity_status, created_at DESC);

-- -------------------------------------------------------
-- Feedback Automation Log
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS feedback_automation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type VARCHAR(50) NOT NULL
        CHECK (run_type IN ('evaluate', 'apply', 'full_cycle')),
    location_id UUID,
    outcomes_evaluated INTEGER DEFAULT 0,
    feedback_signals_generated INTEGER DEFAULT 0,
    feedback_loops_applied INTEGER DEFAULT 0,
    thresholds_adjusted INTEGER DEFAULT 0,
    policies_adjusted INTEGER DEFAULT 0,
    run_duration_ms NUMERIC(10,2),
    errors JSONB DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_auto_location
    ON feedback_automation_log (location_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_auto_status
    ON feedback_automation_log (status, started_at DESC);

-- -------------------------------------------------------
-- Feedback Automation Config
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS feedback_automation_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID UNIQUE,
    eval_interval_hours INTEGER NOT NULL DEFAULT 24,
    max_adjustments_per_run INTEGER NOT NULL DEFAULT 5,
    auto_apply BOOLEAN NOT NULL DEFAULT FALSE,
    dry_run BOOLEAN NOT NULL DEFAULT TRUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------
-- Improvement Rate
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS improvement_rate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    metric_name VARCHAR(100) NOT NULL,
    metric_domain VARCHAR(50),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,

    current_value NUMERIC(10,4),
    prior_value NUMERIC(10,4),
    baseline_value NUMERIC(10,4),

    absolute_change NUMERIC(10,4),
    pct_change NUMERIC(8,4),
    change_from_baseline NUMERIC(8,4),

    trend_direction VARCHAR(20)
        CHECK (trend_direction IN ('improving', 'stable', 'degrading')),
    trend_strength NUMERIC(3,2),
    periods_in_trend INTEGER,

    learning_rate NUMERIC(8,4),
    estimated_plateau NUMERIC(10,4),
    projected_plateau_periods INTEGER,

    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_improvement_rate_location
    ON improvement_rate (location_id, metric_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_improvement_rate_domain
    ON improvement_rate (metric_domain, metric_name);

-- -------------------------------------------------------
-- Threshold Adjustment Log
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS threshold_adjustment_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    threshold_id UUID NOT NULL,
    location_id UUID NOT NULL,

    previous_value NUMERIC(10,4),
    new_value NUMERIC(10,4),
    adjustment_pct NUMERIC(5,2),

    evidence_type VARCHAR(50) NOT NULL
        CHECK (evidence_type IN (
            'false_positive', 'false_negative', 'outcome_feedback',
            'threshold_analysis'
        )),
    evidence_summary JSONB DEFAULT '{}',
    adjustment_count INTEGER NOT NULL DEFAULT 1,

    within_safety_bounds BOOLEAN NOT NULL DEFAULT TRUE,
    min_bound NUMERIC(10,4),
    max_bound NUMERIC(10,4),

    auto_applied BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMPTZ,

    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_threshold_adj_location
    ON threshold_adjustment_log (location_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_threshold_adj_threshold
    ON threshold_adjustment_log (threshold_id, created_at DESC);

-- -------------------------------------------------------
-- Insight Transfer
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS insight_transfer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_domain VARCHAR(50) NOT NULL,
    source_event_type VARCHAR(100) NOT NULL,
    source_event_id UUID,
    target_domain VARCHAR(50) NOT NULL,
    source_insight JSONB NOT NULL,
    target_applicability NUMERIC(3,2),
    transfer_status VARCHAR(20) NOT NULL DEFAULT 'detected'
        CHECK (transfer_status IN (
            'detected', 'pending_review', 'applied',
            'rejected', 'not_applicable'
        )),
    target_action_taken JSONB DEFAULT '{}',
    outcome VARCHAR(20)
        CHECK (outcome IS NULL OR outcome IN (
            'helpful', 'not_helpful', 'pending'
        )),
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_insight_transfer_source
    ON insight_transfer (source_domain, source_event_type);
CREATE INDEX IF NOT EXISTS idx_insight_transfer_target
    ON insight_transfer (target_domain, transfer_status);

-- -------------------------------------------------------
-- Cross-Domain Rule
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS cross_domain_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_domain VARCHAR(50) NOT NULL,
    target_domain VARCHAR(50) NOT NULL,
    source_event_pattern VARCHAR(200) NOT NULL,
    target_action_template JSONB NOT NULL,
    applicability_conditions JSONB DEFAULT '{}',
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.5,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cross_domain_rule_lookup
    ON cross_domain_rule (source_domain, source_event_pattern)
    WHERE enabled;

-- -------------------------------------------------------
-- ML Retrain Schedule
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS ml_retrain_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL,
    location_id UUID,
    retrain_interval_days INTEGER NOT NULL DEFAULT 30,
    accuracy_threshold NUMERIC(5,2) NOT NULL DEFAULT 20.0,
    auto_retrain BOOLEAN NOT NULL DEFAULT FALSE,
    last_retrain_at TIMESTAMPTZ,
    next_retrain_at TIMESTAMPTZ,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ml_retrain_schedule_unique
    ON ml_retrain_schedule (model_name, COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- -------------------------------------------------------
-- ML Retrain Log
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS ml_retrain_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL,
    location_id UUID,
    trigger_reason VARCHAR(100) NOT NULL,
    trigger_metric VARCHAR(100),
    trigger_value NUMERIC(10,4),
    accuracy_before NUMERIC(5,2),
    accuracy_after NUMERIC(5,2),
    improvement_pct NUMERIC(5,2),
    training_duration_ms NUMERIC(10,2),
    training_samples INTEGER,
    model_version VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'running', 'completed', 'failed'
        )),
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ml_retrain_log_model
    ON ml_retrain_log (model_name, started_at DESC);

-- -------------------------------------------------------
-- Growth Curve Analysis
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS growth_curve_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    metric_name VARCHAR(100) NOT NULL,

    curve_type VARCHAR(30) NOT NULL DEFAULT 'insufficient_data'
        CHECK (curve_type IN (
            'exponential', 'linear', 'logarithmic', 's_curve',
            'declining', 'oscillating', 'insufficient_data'
        )),

    inflection_point NUMERIC(10,4),
    inflection_date TIMESTAMPTZ,
    growth_rate NUMERIC(8,6),
    carrying_capacity NUMERIC(10,4),
    current_position_pct NUMERIC(5,2),

    tipping_point_risk NUMERIC(3,2),
    tipping_point_metric VARCHAR(100),
    days_to_tipping_point INTEGER,

    current_velocity NUMERIC(10,4),
    velocity_change_pct NUMERIC(5,2),
    acceleration NUMERIC(8,4),

    data_points_used INTEGER,
    fit_quality NUMERIC(3,2),
    confidence NUMERIC(3,2),

    metadata JSONB DEFAULT '{}',
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_growth_curve_location
    ON growth_curve_analysis (location_id, metric_name, analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_growth_curve_type
    ON growth_curve_analysis (curve_type)
    WHERE curve_type != 'insufficient_data';

-- -------------------------------------------------------
-- Paradigm Shift Detection
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS paradigm_shift_detection (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,

    shift_type VARCHAR(50) NOT NULL
        CHECK (shift_type IN (
            'approach_obsolescence', 'diminishing_returns',
            'new_paradigm_available', 'complexity_exhaustion',
            'ceiling_reached', 'paradigm_shift_needed'
        )),
    source_domain VARCHAR(50) NOT NULL,
    current_approach VARCHAR(200),
    recommended_approach VARCHAR(200),
    evidence JSONB NOT NULL,
    urgency VARCHAR(20)
        CHECK (urgency IN (
            'immediate', 'short_term', 'long_term', 'monitoring'
        )),
    confidence NUMERIC(3,2),
    mindstep_number INTEGER,
    previous_mindstep_interval_days INTEGER,
    predicted_next_shift_days INTEGER,

    status VARCHAR(20) NOT NULL DEFAULT 'detected'
        CHECK (status IN (
            'detected', 'acknowledged', 'acted_on',
            'dismissed', 'superseded'
        )),
    action_taken JSONB DEFAULT '{}',
    outcome VARCHAR(20)
        CHECK (outcome IS NULL OR outcome IN (
            'successful', 'partial', 'failed', 'pending'
        )),
    resolved_at TIMESTAMPTZ,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paradigm_shift_domain
    ON paradigm_shift_detection (source_domain, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_paradigm_shift_urgency
    ON paradigm_shift_detection (urgency, status)
    WHERE status = 'detected';

-- -------------------------------------------------------
-- Meta-Learning Strategy
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS meta_learning_strategy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(200) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL
        CHECK (strategy_type IN (
            'threshold_tuning', 'model_retraining',
            'sampling_adjustment', 'approach_switch',
            'cross_domain_transfer', 'escalation'
        )),
    domain VARCHAR(50),
    context_conditions JSONB NOT NULL DEFAULT '{}',
    effectiveness_score NUMERIC(5,2) DEFAULT 0.0,
    applications_count INTEGER DEFAULT 0,
    successes_count INTEGER DEFAULT 0,
    last_applied_at TIMESTAMPTZ,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meta_strategy_effectiveness
    ON meta_learning_strategy (strategy_type, effectiveness_score DESC);
CREATE INDEX IF NOT EXISTS idx_meta_strategy_domain
    ON meta_learning_strategy (domain, enabled);

-- -------------------------------------------------------
-- Meta-Learning Application
-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS meta_learning_application (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL,
    location_id UUID,
    context JSONB NOT NULL DEFAULT '{}',
    outcome VARCHAR(20)
        CHECK (outcome IN ('success', 'partial', 'failure', 'pending')),
    outcome_evidence JSONB DEFAULT '{}',
    effectiveness_delta NUMERIC(5,2),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    outcome_measured_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meta_application_strategy
    ON meta_learning_application (strategy_id, applied_at DESC);
