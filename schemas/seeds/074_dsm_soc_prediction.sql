-- ============================================================
-- Seeds: Pilot data for DSM/SOC prediction
-- ============================================================

-- SOC prediction model seed
INSERT INTO soc_prediction_model (
    id, model_name, model_type, training_date,
    training_samples, training_fields, feature_count,
    cv_r_squared, cv_rmse, cv_mec,
    field_level_r_squared, field_level_rmse,
    depth_strategy, depth_range, status,
    hyperparameters, notes
) VALUES (
    'a0000000-0000-0000-0000-000000007401',
    'ATLAS-SOC v1 Pilot',
    'xgboost',
    '2026-07-09',
    0, 0, 0,
    NULL, NULL, NULL,
    NULL, NULL,
    'full_column', '0-30', 'draft',
    '{"n_estimators": 500, "learning_rate": 0.05, "max_depth": 8, "subsample": 0.8, "colsample_bytree": 0.8}'::jsonb,
    'Pilot model placeholder — requires training data with co-located soil samples and remote sensing features'
) ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    notes = EXCLUDED.notes;
