BEGIN;

CREATE TABLE IF NOT EXISTS prediction_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table VARCHAR(100) NOT NULL,
    source_id UUID NOT NULL,
    source_point_key VARCHAR(255) NOT NULL DEFAULT 'scalar',
    domain VARCHAR(50) NOT NULL,
    metric_key VARCHAR(100) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    location_id UUID NOT NULL REFERENCES location(id),
    crop_id UUID REFERENCES crop(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    plot_id UUID REFERENCES plot(id),
    model_name VARCHAR(200) NOT NULL,
    model_version VARCHAR(100) NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    target_start TIMESTAMPTZ NOT NULL,
    target_end TIMESTAMPTZ NOT NULL,
    horizon_seconds BIGINT NOT NULL,
    predicted_value NUMERIC(20,8) NOT NULL,
    probability NUMERIC(8,7),
    interval_low NUMERIC(20,8),
    interval_high NUMERIC(20,8),
    confidence_level NUMERIC(8,7),
    inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    input_hash VARCHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    UNIQUE (source_table, source_id, source_point_key),
    CHECK (status IN ('draft','submitted','verified','published','rejected')),
    CHECK (target_end >= target_start),
    CHECK (horizon_seconds >= 0),
    CHECK (interval_low IS NULL OR interval_high IS NULL OR interval_low <= interval_high),
    CHECK (probability IS NULL OR probability BETWEEN 0 AND 1),
    CHECK (confidence_level IS NULL OR confidence_level > 0 AND confidence_level <= 1)
);

CREATE TABLE IF NOT EXISTS prediction_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES prediction_ledger(id) ON DELETE CASCADE,
    actual_source_table VARCHAR(100) NOT NULL,
    actual_source_id UUID NOT NULL,
    actual_timestamp TIMESTAMPTZ NOT NULL,
    actual_value NUMERIC(20,8) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    source_status VARCHAR(50),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    supersedes_id UUID REFERENCES prediction_outcome(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    CHECK (status IN ('draft','submitted','verified','published','rejected')),
    CHECK (status NOT IN ('verified','published') OR (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_prediction_active_outcome
    ON prediction_outcome(prediction_id)
    WHERE status IN ('verified','published');

CREATE TABLE IF NOT EXISTS prediction_evaluation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES prediction_ledger(id) ON DELETE CASCADE,
    outcome_id UUID NOT NULL REFERENCES prediction_outcome(id) ON DELETE CASCADE,
    signed_error NUMERIC(20,8) NOT NULL,
    absolute_error NUMERIC(20,8) NOT NULL,
    squared_error NUMERIC(30,12) NOT NULL,
    absolute_percentage_error NUMERIC(12,6),
    within_interval BOOLEAN,
    brier_score NUMERIC(12,10),
    evaluation_version VARCHAR(50) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (prediction_id, outcome_id, evaluation_version),
    CHECK (brier_score IS NULL OR brier_score BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS prediction_calibration_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(50) NOT NULL,
    metric_key VARCHAR(100),
    model_name VARCHAR(200),
    model_version VARCHAR(100),
    minimum_sample_size INTEGER NOT NULL DEFAULT 20 CHECK (minimum_sample_size > 0),
    maximum_mape NUMERIC(8,4),
    maximum_abs_bias_pct NUMERIC(8,4),
    minimum_interval_coverage NUMERIC(8,4),
    maximum_brier_score NUMERIC(8,6),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to TIMESTAMPTZ,
    created_by UUID
);

CREATE TABLE IF NOT EXISTS prediction_calibration_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(50) NOT NULL,
    metric_key VARCHAR(100) NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    model_version VARCHAR(100) NOT NULL,
    location_id UUID REFERENCES location(id),
    crop_id UUID REFERENCES crop(id),
    horizon_bucket VARCHAR(50) NOT NULL,
    policy_id UUID REFERENCES prediction_calibration_policy(id),
    sample_size INTEGER NOT NULL,
    mae NUMERIC(20,8),
    rmse NUMERIC(20,8),
    mape NUMERIC(12,6),
    signed_bias NUMERIC(20,8),
    bias_pct NUMERIC(12,6),
    interval_coverage NUMERIC(8,6),
    mean_brier_score NUMERIC(12,10),
    gate_result VARCHAR(20) NOT NULL,
    failure_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    evaluation_cutoff TIMESTAMPTZ NOT NULL,
    calculation_version VARCHAR(50) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (gate_result IN ('pass','fail','insufficient_data','stale'))
);

CREATE INDEX IF NOT EXISTS idx_prediction_ledger_scope
    ON prediction_ledger(model_name, model_version, metric_key, location_id, crop_id, horizon_seconds);
CREATE INDEX IF NOT EXISTS idx_prediction_evaluation_prediction ON prediction_evaluation(prediction_id);
CREATE INDEX IF NOT EXISTS idx_prediction_calibration_scope
    ON prediction_calibration_assessment(model_name, model_version, metric_key, computed_at DESC);

CREATE TABLE IF NOT EXISTS reference_class (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_key VARCHAR(150) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    metric_key VARCHAR(100) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    population_definition TEXT NOT NULL,
    inclusion_criteria JSONB NOT NULL,
    exclusion_criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    geography VARCHAR(150),
    climate_zone VARCHAR(100),
    production_system VARCHAR(150),
    species_or_crop VARCHAR(150),
    sample_size INTEGER NOT NULL CHECK (sample_size > 0),
    p10 NUMERIC(20,8),
    p25 NUMERIC(20,8),
    median NUMERIC(20,8) NOT NULL,
    p75 NUMERIC(20,8),
    p90 NUMERIC(20,8),
    failure_rate NUMERIC(8,7) CHECK (failure_rate IS NULL OR failure_rate BETWEEN 0 AND 1),
    source_citation TEXT NOT NULL,
    source_url TEXT,
    source_published_at DATE,
    evidence_maturity_level INTEGER NOT NULL DEFAULT 1 CHECK (evidence_maturity_level BETWEEN 0 AND 6),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    submitted_by UUID,
    submitted_at TIMESTAMPTZ,
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    supersedes_id UUID REFERENCES reference_class(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (reference_key, version),
    CHECK (status IN ('draft','submitted','verified','published','rejected')),
    CHECK (p10 IS NULL OR p10 <= median),
    CHECK (p90 IS NULL OR median <= p90),
    CHECK (status NOT IN ('verified','published') OR (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS outside_view_comparison (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES prediction_ledger(id) ON DELETE CASCADE,
    reference_class_id UUID NOT NULL REFERENCES reference_class(id),
    inside_estimate NUMERIC(20,8) NOT NULL,
    reference_median NUMERIC(20,8) NOT NULL,
    reference_adverse NUMERIC(20,8),
    deviation_pct NUMERIC(12,6),
    selection_rationale TEXT NOT NULL,
    deviation_rationale TEXT,
    disconfirming_evidence TEXT,
    fit_dimensions JSONB NOT NULL DEFAULT '{}'::jsonb,
    fit_status VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (prediction_id, reference_class_id),
    CHECK (fit_status IN ('good','partial','poor','insufficient_evidence')),
    CHECK (status IN ('draft','submitted','verified','published','rejected')),
    CHECK (deviation_pct IS NULL OR ABS(deviation_pct) <= 10 OR NULLIF(BTRIM(deviation_rationale), '') IS NOT NULL),
    CHECK (status NOT IN ('verified','published') OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);

CREATE OR REPLACE VIEW v_prediction_calibration_summary AS
SELECT DISTINCT ON (domain, metric_key, model_name, model_version, location_id, crop_id, horizon_bucket)
    *
FROM prediction_calibration_assessment
ORDER BY domain, metric_key, model_name, model_version, location_id, crop_id, horizon_bucket, computed_at DESC;

CREATE OR REPLACE FUNCTION block_materially_uncalibrated_forecast() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'published' AND OLD.status IS DISTINCT FROM 'published' AND EXISTS (
        SELECT 1
        FROM forecast_output fo
        JOIN prediction_ledger pl ON pl.source_table = 'forecast_output' AND pl.source_id = fo.id
        JOIN LATERAL (
            SELECT pca.gate_result
            FROM prediction_calibration_assessment pca
            WHERE pca.model_name = pl.model_name
              AND pca.model_version = pl.model_version
              AND pca.metric_key = pl.metric_key
            ORDER BY pca.computed_at DESC LIMIT 1
        ) latest ON TRUE
        WHERE fo.scenario_id = NEW.id AND latest.gate_result = 'fail'
    ) THEN
        RAISE EXCEPTION 'forecast publication blocked by materially poor calibration';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_forecast_calibration_gate ON forecast_scenario;
CREATE TRIGGER trg_forecast_calibration_gate
BEFORE UPDATE OF status ON forecast_scenario
FOR EACH ROW EXECUTE FUNCTION block_materially_uncalibrated_forecast();

COMMIT;
