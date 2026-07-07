-- ============================================================
-- 049_model_validation.sql — Seeds: metrics, Adelphi pilot data
-- ============================================================

-- New metric definitions
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('forecast_mae', 'Forecast Mean Absolute Error', 'Mean absolute error between predicted and actual values for key outputs.', 'avg(absolute_error) from prediction_accuracy_record where status in verified/published', ARRAY['prediction_accuracy_record'], 'Use published prediction accuracy records with actual values.', 'Exclude records without actual_value.', 'unit_of_metric', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['model_validation', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('forecast_accuracy_pct', 'Forecast Accuracy %', '100 minus mean absolute percentage error for yield predictions.', '100 - avg(percentage_error) from prediction_accuracy_record where metric_name = yield and status in verified/published', ARRAY['prediction_accuracy_record'], 'Use published yield prediction accuracy records.', 'Exclude records without percentage_error.', 'percentage', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['model_validation', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
ON CONFLICT (metric_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    formula = EXCLUDED.formula,
    source_tables = EXCLUDED.source_tables,
    inclusion_rules = EXCLUDED.inclusion_rules,
    exclusion_rules = EXCLUDED.exclusion_rules,
    unit = EXCLUDED.unit,
    data_type = EXCLUDED.data_type,
    owner = EXCLUDED.owner,
    update_frequency = EXCLUDED.update_frequency,
    active = EXCLUDED.active,
    validation_tests = EXCLUDED.validation_tests,
    report_usage = EXCLUDED.report_usage,
    deprecation_policy = EXCLUDED.deprecation_policy;

-- Adelphi pilot: prediction accuracy records
INSERT INTO prediction_accuracy_record (
    id, location_id, zone_id,
    model_type, model_name, prediction_date, actual_date,
    predicted_value, actual_value, absolute_error, percentage_error,
    mae, mape, sample_size,
    metric_name, unit, input_variables, notes,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004910',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'yield_prediction', 'Adelphi Lettuce Yield Model',
 '2025-12-15', '2025-12-20',
 1200.00, 1080.00, 120.00, 11.11,
 120.00, 11.11, 1,
 'lettuce_yield_kg', 'kg',
 '{"planting_density": 25, "bed_area_sqm": 4.0, "bed_count": 8, "rainfall_mm": 45}'::jsonb,
 'Yield prediction for lettuce Cycle 1. Actual was 10% below predicted due to late-season aphid pressure.',
 'published', 'pilot_seed', 'adelphi-pred-yield-lettuce',
 '{"record_type":"prediction_accuracy_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004911',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'pest_dynamics', 'Adelphi Pest Dynamics Model',
 '2026-01-05', '2026-02-10',
 15.00, 12.00, 3.00, 25.00,
 3.00, 25.00, 1,
 'aphid_outbreak_probability_pct', 'percentage',
 '{"predator_release_count": 200, "temperature_c": 27.5, "humidity_pct": 72.0}'::jsonb,
 'Pest dynamics prediction for aphid outbreak. Actual reduction was 68% vs predicted 68% — model performed well.',
 'published', 'pilot_seed', 'adelphi-pred-pest-aphid',
 '{"record_type":"prediction_accuracy_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004912',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'carbon_projection', 'Adelphi Carbon Sequestration Model',
 '2025-10-01', '2026-03-10',
 2.50, 2.80, 0.30, 10.71,
 0.30, 10.71, 1,
 'soil_carbon_delta_t_ha', 'tonnes_per_hectare',
 '{"biochar_applied_kg": 120, "leaf_litter_kg": 250, "compost_kg": 80}'::jsonb,
 'Carbon sequestration projection. Actual soil carbon increase slightly exceeded prediction.',
 'published', 'pilot_seed', 'adelphi-pred-carbon-soil',
 '{"record_type":"prediction_accuracy_record","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    predicted_value = EXCLUDED.predicted_value,
    actual_value = EXCLUDED.actual_value,
    absolute_error = EXCLUDED.absolute_error,
    percentage_error = EXCLUDED.percentage_error,
    updated_at = NOW();

-- Adelphi pilot: feature importance records
INSERT INTO feature_importance_record (
    id, location_id,
    model_type, analysis_date,
    feature_name, importance_score, direction,
    correlation_coefficient, p_value, sample_size,
    notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004920',
 'a0000000-0000-0000-0000-000000000001',
 'yield_prediction', '2026-03-10',
 'rainfall_mm', 0.85, 'positive',
 0.82, 0.003, 6,
 'Rainfall is the strongest predictor of lettuce yield across the pilot season.',
 'published', 'pilot_seed', 'adelphi-feat-rainfall-yield',
 '{"record_type":"feature_importance_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004921',
 'a0000000-0000-0000-0000-000000000001',
 'yield_prediction', '2026-03-10',
 'temperature_c', 0.62, 'positive',
 0.58, 0.021, 6,
 'Temperature positively correlates with yield but with diminishing returns above 30C.',
 'published', 'pilot_seed', 'adelphi-feat-temp-yield',
 '{"record_type":"feature_importance_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004922',
 'a0000000-0000-0000-0000-000000000001',
 'pest_dynamics', '2026-03-10',
 'humidity_pct', 0.78, 'positive',
 0.75, 0.008, 6,
 'Humidity is the strongest predictor of aphid outbreak probability.',
 'published', 'pilot_seed', 'adelphi-feat-humidity-pest',
 '{"record_type":"feature_importance_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004923',
 'a0000000-0000-0000-0000-000000000001',
 'pest_dynamics', '2026-03-10',
 'predator_release_count', 0.71, 'negative',
 -0.68, 0.014, 6,
 'Predator release count inversely predicts pest outbreak probability.',
 'published', 'pilot_seed', 'adelphi-feat-predator-pest',
 '{"record_type":"feature_importance_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004924',
 'a0000000-0000-0000-0000-000000000001',
 'carbon_projection', '2026-03-10',
 'biochar_applied_kg', 0.90, 'positive',
 0.88, 0.001, 6,
 'Biochar application is the strongest predictor of soil carbon increase.',
 'published', 'pilot_seed', 'adelphi-feat-biochar-carbon',
 '{"record_type":"feature_importance_record","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    importance_score = EXCLUDED.importance_score,
    direction = EXCLUDED.direction,
    correlation_coefficient = EXCLUDED.correlation_coefficient,
    p_value = EXCLUDED.p_value,
    updated_at = NOW();
