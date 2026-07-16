-- ============================================================
-- 296_sequential_experiment_analysis.sql
-- Reproducible sequential experiment evaluations and stopping records.
-- ============================================================

CREATE TABLE IF NOT EXISTS solution_experiment_analysis_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES solution_experiment(id) ON DELETE CASCADE,
    metric_key VARCHAR(120) NOT NULL,
    baseline_count INTEGER NOT NULL DEFAULT 0,
    treatment_count INTEGER NOT NULL DEFAULT 0,
    baseline_mean NUMERIC(15,6),
    treatment_mean NUMERIC(15,6),
    effect_estimate NUMERIC(15,6),
    standard_error NUMERIC(15,6),
    lower_bound NUMERIC(15,6),
    upper_bound NUMERIC(15,6),
    posterior_probability_benefit NUMERIC(12,10),
    adverse_event_count INTEGER NOT NULL DEFAULT 0,
    decision VARCHAR(30) NOT NULL CHECK (decision IN ('continue', 'benefit', 'futility', 'safety_stop', 'max_duration', 'insufficient_data')),
    stopping_reason TEXT NOT NULL,
    analysis_version VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_solution_experiment_analysis
    ON solution_experiment_analysis_run(experiment_id, created_at DESC);

COMMENT ON TABLE solution_experiment_analysis_run IS 'Sequential, reproducible experiment analysis with effect uncertainty, benefit probability, safety, and stopping decision';
