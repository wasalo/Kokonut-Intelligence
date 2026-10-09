-- ============================================================
-- 092_if_efficiency_metrics.sql
-- Efficiency ratio and chemical use reduction metrics
-- for Integrated Farming Framework (IF8, IF9)
-- ============================================================

BEGIN;

-- IF8: Input-Output Efficiency Ratios
INSERT INTO metric_definition (metric_key, display_name, formula, source_tables, validation_tests, unit, data_type, update_frequency) VALUES
    ('water_use_efficiency_kg_m3', 'Water Use Efficiency (kg/m³)', 'harvest_yield_kg / total_water_m3', ARRAY['harvest_yield_observation', 'irrigation_event'], '["value >= 0", "total_water_m3 > 0"]', 'kg/m³', 'numeric', 'seasonal'),
    ('energy_use_efficiency_kg_kwh', 'Energy Use Efficiency (kg/kWh)', 'harvest_yield_kg / total_energy_kwh', ARRAY['harvest_yield_observation', 'energy_reading'], '["value >= 0", "total_energy_kwh > 0"]', 'kg/kWh', 'numeric', 'seasonal'),
    ('fertilizer_use_efficiency_kg_kg', 'Fertilizer Use Efficiency (kg yield/kg input)', 'harvest_yield_kg / total_fertilizer_kg', ARRAY['harvest_yield_observation', 'nutrient_input'], '["value >= 0", "total_fertilizer_kg > 0"]', 'kg/kg', 'numeric', 'seasonal'),
    ('land_productivity_usd_ha', 'Land Productivity (USD/ha)', 'total_revenue_usd / area_ha', ARRAY['revenue_event', 'location'], '["value >= 0"]', 'USD/ha', 'numeric', 'seasonal'),
    ('nutrient_use_efficiency_pct', 'Nutrient Use Efficiency %', '(nutrient_removal_kg / nutrient_input_kg) * 100', ARRAY['nutrient_budget'], '["0 <= value <= 100"]', '%', 'numeric', 'seasonal')
ON CONFLICT (metric_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    formula = EXCLUDED.formula,
    source_tables = EXCLUDED.source_tables,
    unit = EXCLUDED.unit,
    data_type = EXCLUDED.data_type,
    update_frequency = EXCLUDED.update_frequency;

-- IF9: Chemical Use Reduction Tracking
INSERT INTO metric_definition (metric_key, display_name, formula, source_tables, validation_tests, unit, data_type, update_frequency) VALUES
    ('pesticide_intensity_kg_ha', 'Pesticide Intensity (kg active ingredient/ha)', 'total_pesticide_kg / area_ha', ARRAY['pesticide_application_log', 'location'], '["value >= 0"]', 'kg/ha', 'numeric', 'monthly'),
    ('chemical_use_reduction_pct', 'Chemical Use Reduction %', '((previous_period_kg - current_period_kg) / previous_period_kg) * 100', ARRAY['pesticide_application_log'], '["-100 <= value <= 100"]', '%', 'numeric', 'quarterly'),
    ('biological_control_pct', 'Biological Control Share %', '(biological_interventions / total_interventions) * 100', ARRAY['pest_intervention'], '["0 <= value <= 100"]', '%', 'numeric', 'quarterly'),
    ('ipm_compliance_score', 'IPM Compliance Score', 'scoring(scouting_frequency, threshold_adherence, intervention_ladder, record_keeping)', ARRAY['pest_scouting_record', 'pest_action_threshold', 'pest_intervention'], '["0 <= value <= 100"]', 'score', 'numeric', 'quarterly')
ON CONFLICT (metric_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    formula = EXCLUDED.formula,
    source_tables = EXCLUDED.source_tables,
    unit = EXCLUDED.unit,
    data_type = EXCLUDED.data_type,
    update_frequency = EXCLUDED.update_frequency;

-- Dashboard definitions for IF efficiency metrics
INSERT INTO dashboard_dataset (id, name, description, dataset_type, query_sql, refresh_interval_minutes, status, metadata) VALUES
    ('a0000000-0000-0000-0000-000000009201', 'Integrated Farming Efficiency', 'Input-output efficiency ratios and chemical use reduction trends across the farm.', 'if_efficiency', NULL, 1440, 'published', '{"owner":"impact_guild","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata;

COMMIT;
