-- ============================================================
-- 183_predictive_process.sql - Predictive BPM forecasts
-- ============================================================
-- Stores per-case process predictions: given an in-flight governed
-- entity, predict remaining time to 'published' and the probability
-- of breaching an SLA target. Models are empirical (historical
-- remaining-time distributions per state) and versioned by date.
-- Reuses lifecycle_transition (179) as the training event log.

CREATE TABLE IF NOT EXISTS predictive_process_forecast (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    current_state VARCHAR(50),
    age_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
    predicted_remaining_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
    breach_probability DOUBLE PRECISION,
    sla_target_hours DOUBLE PRECISION,
    model_version VARCHAR(20) NOT NULL,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ppf_entity ON predictive_process_forecast(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_ppf_breach ON predictive_process_forecast(entity_type, breach_probability);
