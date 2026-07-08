-- ============================================================
-- 049_model_validation.sql — Prediction accuracy tracking and model validation
-- ============================================================

-- Prediction accuracy record: stores predicted vs actual comparisons
CREATE TABLE IF NOT EXISTS prediction_accuracy_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    model_type VARCHAR(100) NOT NULL,
    model_name VARCHAR(255),
    prediction_date DATE NOT NULL,
    actual_date DATE,
    predicted_value NUMERIC(15,4),
    actual_value NUMERIC(15,4),
    absolute_error NUMERIC(15,4),
    squared_error NUMERIC(15,6),
    percentage_error NUMERIC(8,4),
    mae NUMERIC(15,4),
    rmse NUMERIC(15,4),
    mape NUMERIC(8,4),
    r_squared NUMERIC(6,4),
    sample_size INTEGER,
    input_variables JSONB DEFAULT '{}',
    metric_name VARCHAR(100),
    unit VARCHAR(50),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'model-validation-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_pred_accuracy_location ON prediction_accuracy_record(location_id);
CREATE INDEX IF NOT EXISTS idx_pred_accuracy_model_type ON prediction_accuracy_record(model_type);
CREATE INDEX IF NOT EXISTS idx_pred_accuracy_date ON prediction_accuracy_record(prediction_date);
CREATE INDEX IF NOT EXISTS idx_pred_accuracy_metric ON prediction_accuracy_record(metric_name);
CREATE INDEX IF NOT EXISTS idx_pred_accuracy_status ON prediction_accuracy_record(status);

ALTER TABLE prediction_accuracy_record DROP CONSTRAINT IF EXISTS chk_pred_accuracy_model_type;
ALTER TABLE prediction_accuracy_record ADD CONSTRAINT chk_pred_accuracy_model_type CHECK (model_type IN (
    'yield_prediction', 'pest_dynamics', 'carbon_projection',
    'nutrient_cycling', 'population_dynamics', 'energy_flow',
    'water_balance', 'other'
));

ALTER TABLE prediction_accuracy_record DROP CONSTRAINT IF EXISTS chk_pred_accuracy_status;
ALTER TABLE prediction_accuracy_record ADD CONSTRAINT chk_pred_accuracy_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Feature importance record: stores sensitivity analysis results
CREATE TABLE IF NOT EXISTS feature_importance_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    model_type VARCHAR(100) NOT NULL,
    analysis_date DATE NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    importance_score NUMERIC(6,4) CHECK (importance_score >= 0 AND importance_score <= 1),
    direction VARCHAR(50),
    correlation_coefficient NUMERIC(6,4),
    p_value NUMERIC(8,6),
    sample_size INTEGER,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'model-validation-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_feature_imp_location ON feature_importance_record(location_id);
CREATE INDEX IF NOT EXISTS idx_feature_imp_model_type ON feature_importance_record(model_type);
CREATE INDEX IF NOT EXISTS idx_feature_imp_date ON feature_importance_record(analysis_date);
CREATE INDEX IF NOT EXISTS idx_feature_imp_feature ON feature_importance_record(feature_name);
CREATE INDEX IF NOT EXISTS idx_feature_imp_status ON feature_importance_record(status);

ALTER TABLE feature_importance_record DROP CONSTRAINT IF EXISTS chk_feature_imp_model_type;
ALTER TABLE feature_importance_record ADD CONSTRAINT chk_feature_imp_model_type CHECK (model_type IN (
    'yield_prediction', 'pest_dynamics', 'carbon_projection',
    'nutrient_cycling', 'population_dynamics', 'energy_flow',
    'water_balance', 'other'
));

ALTER TABLE feature_importance_record DROP CONSTRAINT IF EXISTS chk_feature_imp_direction;
ALTER TABLE feature_importance_record ADD CONSTRAINT chk_feature_imp_direction CHECK (
    direction IS NULL OR direction IN ('positive', 'negative', 'neutral')
);

ALTER TABLE feature_importance_record DROP CONSTRAINT IF EXISTS chk_feature_imp_status;
ALTER TABLE feature_importance_record ADD CONSTRAINT chk_feature_imp_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Public-safe views
CREATE OR REPLACE VIEW v_public_prediction_accuracy AS
SELECT
    par.id,
    par.location_id,
    l.name AS location_name,
    par.model_type,
    par.model_name,
    par.prediction_date,
    par.actual_date,
    par.predicted_value,
    par.actual_value,
    par.absolute_error,
    par.mae,
    par.rmse,
    par.mape,
    par.r_squared,
    par.sample_size,
    par.metric_name,
    par.unit,
    par.notes,
    par.status
FROM prediction_accuracy_record par
JOIN location l ON l.id = par.location_id
WHERE l.status = 'active'
  AND par.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_feature_importance AS
SELECT
    fir.id,
    fir.location_id,
    l.name AS location_name,
    fir.model_type,
    fir.analysis_date,
    fir.feature_name,
    fir.importance_score,
    fir.direction,
    fir.correlation_coefficient,
    fir.p_value,
    fir.sample_size,
    fir.notes,
    fir.status
FROM feature_importance_record fir
JOIN location l ON l.id = fir.location_id
WHERE l.status = 'active'
  AND fir.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('model-validation-v1', 'Prediction accuracy tracking, feature importance, and model validation views', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
