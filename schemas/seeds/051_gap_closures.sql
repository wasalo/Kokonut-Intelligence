-- ============================================================
-- 051_gap_closures.sql — Seeds: Q5 irrigation/rainfall data, metrics
-- ============================================================

-- Update existing resource_consumption records with irrigation/rainfall data (Q5)
UPDATE resource_consumption SET
    irrigation_mm_used = 50.00,
    rainfall_mm_during_period = 120.00
WHERE id = 'a0000000-0000-0000-0000-000000004740';

UPDATE resource_consumption SET
    irrigation_mm_used = 40.00,
    rainfall_mm_during_period = 85.00
WHERE id = 'a0000000-0000-0000-0000-000000004742';

-- New metric definitions for gap closures
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('yield_delta_kg', 'Yield Delta (kg)', 'Difference between actual and predicted yield per crop cycle.', 'actual_yield - expected_yield from crop_cycle where status in completed/harvested', ARRAY['crop_cycle'], 'Use completed or harvested crop cycles with both expected and actual yield.', 'Exclude cycles without actual yield.', 'kg', 'numeric', 'Ecology Guild', 1, 'per_cycle', TRUE, '[]'::jsonb, ARRAY['ecological_modeling', 'yield_management'], 'Supersede through metric_version before changing public interpretation.'),
('species_richness_per_ha', 'Species Richness per Hectare', 'Number of unique species per hectare of cultivated area.', 'count(distinct species_name) / sum(plot.area) from species_observation', ARRAY['species_observation', 'plot'], 'Use published species observations with plot area data.', 'Exclude observations without area linkage.', 'species_per_ha', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['ecological_modeling', 'biodiversity'], 'Supersede through metric_version before changing public interpretation.'),
('rainfall_irrigation_delta_mm', 'Rainfall minus Irrigation (mm)', 'Net water balance: rainfall minus irrigation applied.', 'sum(rainfall_mm_during_period) - sum(irrigation_mm_used) from resource_consumption', ARRAY['resource_consumption'], 'Use published resource consumption records with irrigation and rainfall data.', 'Exclude records without both values.', 'mm', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '[]'::jsonb, ARRAY['ecological_modeling', 'water_management'], 'Supersede through metric_version before changing public interpretation.')
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
