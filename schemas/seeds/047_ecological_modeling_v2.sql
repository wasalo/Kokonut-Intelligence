-- ============================================================
-- 047_ecological_modeling_v2.sql — Metrics, dashboards, Adelphi pilot data
-- ============================================================

-- New metric definitions
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('pest_outbreak_probability', 'Pest Outbreak Probability', 'Monthly pest outbreak probability per plot derived from severity, incidence, and weather conditions.', 'avg(outbreak_probability_pct) from pest_observation where status in verified/published', ARRAY['pest_observation'], 'Use published pest observations with severity and incidence data.', 'Exclude draft or rejected observations.', 'percentage', 'numeric', 'Ecology Guild', 1, 'monthly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['ecological_modeling', 'pest_management'], 'Supersede through metric_version before changing public interpretation.'),
('biocontrol_effectiveness_pct', 'Biocontrol Effectiveness %', 'Average pest reduction achieved by predator/biocontrol introductions.', 'avg(pest_reduction_pct) from biocontrol_release where status in verified/published', ARRAY['biocontrol_release'], 'Use published biocontrol releases with follow_up data.', 'Exclude releases without follow_up measurements.', 'percentage', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['ecological_modeling', 'pest_management'], 'Supersede through metric_version before changing public interpretation.'),
('labor_efficiency_kg_per_hour', 'Labor Efficiency (kg/hour)', 'Harvest output per labor hour across crop cycles.', 'sum(harvest_event.quantity) / sum(labor_event.hours_worked)', ARRAY['harvest_event', 'labor_event'], 'Use verified harvest events linked to labor events via crop_cycle_id.', 'Exclude labor events without corresponding harvest data.', 'kg_per_hour', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['ecological_modeling', 'resource_efficiency'], 'Supersede through metric_version before changing public interpretation.'),
('resource_intensity_index', 'Resource Intensity Index', 'Composite energy and water use per kilogram of yield.', '(sum(energy_kwh) + sum(water_liters) / 1000) / sum(harvest_kg)', ARRAY['resource_consumption', 'harvest_event'], 'Use verified resource consumption and harvest records with matching periods.', 'Exclude estimated records where is_estimated = TRUE.', 'index', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['ecological_modeling', 'resource_efficiency'], 'Supersede through metric_version before changing public interpretation.')
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

-- New dashboard datasets
INSERT INTO dashboard_dataset (
    id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata
) VALUES
('a0000000-0000-0000-0000-000000004701', 'Pest Management', 'Monthly pest incidence trends, outbreak probability, and biocontrol effectiveness.', 'pest_management', NULL, 'dashboards/metabase/sql/64_pest_management.sql', 1440, 'published', '{"owner":"ecology_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004702', 'Resource Efficiency', 'Labor, energy, and water efficiency per kilogram of yield by crop.', 'resource_efficiency', NULL, 'dashboards/metabase/sql/65_resource_efficiency.sql', 1440, 'published', '{"owner":"ecology_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Conservation status updates for existing species observations
UPDATE species_observation SET conservation_status = 'least_concern'
WHERE species_name = 'Gallus gallus domesticus' AND conservation_status IS NULL;

UPDATE species_observation SET conservation_status = 'least_concern'
WHERE species_name = 'Passer domesticus' AND conservation_status IS NULL;

UPDATE species_observation SET conservation_status = 'least_concern'
WHERE species_name = 'Apis mellifera' AND conservation_status IS NULL;

-- Adelphi pilot: soil input applications
INSERT INTO soil_input_application (
    id, location_id, plot_id, zone_id, crop_cycle_id,
    application_date, input_type, input_name, quantity_kg,
    application_method, depth_cm, area_m2,
    decomposition_status, residual_pct, residual_measurement_date,
    notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004710',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 NULL,
 '2025-10-05', 'biochar', 'Coconut shell biochar', 120.00,
 'broadcast_and_incorporate', 15.0, 2500.00,
 'partially_decomposed', 72.00, '2026-03-10',
 'Biochar applied to syntropic beds at 48 kg/ha. Residual measurement at 5 months shows 72% remaining.',
 'published', 'pilot_seed', 'adelphi-soil-input-biochar',
 '{"record_type":"soil_input_application","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004711',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 NULL,
 '2025-10-05', 'leaf_litter', 'Inga edulis leaf litter', 250.00,
 'surface_mulch', NULL, 2500.00,
 'partially_decomposed', 45.00, '2026-03-10',
 'Leaf litter from Inga edulis canopy used as surface mulch. 45% residual after 5 months.',
 'published', 'pilot_seed', 'adelphi-soil-input-litter',
 '{"record_type":"soil_input_application","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004712',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 NULL,
 '2025-10-10', 'compost', 'Vermicompost', 80.00,
 'side_dress', 10.0, 2500.00,
 'fully_decomposed', 15.00, '2026-03-10',
 'Vermicompost side-dressed around passion fruit vines. Most decomposed input at 5 months.',
 'published', 'pilot_seed', 'adelphi-soil-input-compost',
 '{"record_type":"soil_input_application","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    input_type = EXCLUDED.input_type,
    quantity_kg = EXCLUDED.quantity_kg,
    residual_pct = EXCLUDED.residual_pct,
    decomposition_status = EXCLUDED.decomposition_status,
    updated_at = NOW();

-- Adelphi pilot: pest observations
INSERT INTO pest_observation (
    id, location_id, plot_id, crop_cycle_id,
    observation_date, pest_species, pest_common_name, pest_category,
    incidence_count, severity, affected_area_pct,
    temperature_c, humidity_pct, rainfall_mm,
    predator_count, natural_enemy_present, outbreak_probability_pct,
    control_action, method, notes,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004720',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 NULL,
 '2025-11-15', 'Spodoptera frugiperda', 'Fall armyworm', 'insect',
 12, 'medium', 8.5,
 27.3, 72.0, 45.0,
 3, TRUE, 35.00,
 'Applied neem-based biopesticide', 'visual',
 'Moderate fall armyworm pressure on lettuce beds. Natural predators (ladybugs) present.',
 'published', 'pilot_seed', 'adelphi-pest-armyworm-nov',
 '{"record_type":"pest_observation","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004721',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 NULL,
 '2026-01-20', 'Spodoptera frugiperda', 'Fall armyworm', 'insect',
 5, 'low', 3.0,
 26.8, 68.0, 30.0,
 8, TRUE, 15.00,
 'No action needed — natural predators controlling population', 'visual',
 'Reduced armyworm pressure after predator population increased.',
 'published', 'pilot_seed', 'adelphi-pest-armyworm-jan',
 '{"record_type":"pest_observation","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004722',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 NULL,
 '2026-02-10', 'Aphis gossypii', 'Cotton aphid', 'insect',
 25, 'high', 15.0,
 28.1, 75.0, 20.0,
 2, FALSE, 65.00,
 'Applied soap-based spray', 'visual',
 'Aphid outbreak on passion fruit vines. High humidity and warm temperatures contributed.',
 'published', 'pilot_seed', 'adelphi-pest-aphid-feb',
 '{"record_type":"pest_observation","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    pest_species = EXCLUDED.pest_species,
    severity = EXCLUDED.severity,
    incidence_count = EXCLUDED.incidence_count,
    outbreak_probability_pct = EXCLUDED.outbreak_probability_pct,
    updated_at = NOW();

-- Adelphi pilot: biocontrol releases
INSERT INTO biocontrol_release (
    id, location_id, plot_id, zone_id, crop_cycle_id,
    release_date, predator_species, predator_common_name, predator_category,
    release_count, target_pest, release_method, release_density_per_m2,
    follow_up_date, follow_up_count, effectiveness_pct, pest_reduction_pct,
    notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004730',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 NULL,
 '2026-01-05', 'Hippodamia convergens', 'Convergent lady beetle', 'predator',
 200, 'Aphis gossypii', 'foliar_release', 0.08,
 '2026-02-10', 145, 72.50, 68.00,
 'Released 200 lady beetles on aphid-infested passion fruit. 145 recovered at follow-up (72.5% retention). 68% aphid reduction observed.',
 'published', 'pilot_seed', 'adelphi-bioctrl-ladybug',
 '{"record_type":"biocontrol_release","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004731',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 NULL,
 '2025-11-20', 'Trichogramma pretiosum', 'Parasitic wasp', 'parasitoid',
 500, 'Spodoptera frugiperda', 'egg_card_release', 0.20,
 '2025-12-20', NULL, 45.00, 42.00,
 'Released 500 Trichogramma wasp cards for armyworm egg parasitism. 45% parasitism rate estimated.',
 'published', 'pilot_seed', 'adelphi-bioctrl-trichogramma',
 '{"record_type":"biocontrol_release","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    predator_species = EXCLUDED.predator_species,
    release_count = EXCLUDED.release_count,
    effectiveness_pct = EXCLUDED.effectiveness_pct,
    pest_reduction_pct = EXCLUDED.pest_reduction_pct,
    updated_at = NOW();

-- Adelphi pilot: resource consumption records
INSERT INTO resource_consumption (
    id, location_id, plot_id, crop_cycle_id,
    period_start, period_end, resource_type, quantity, unit,
    component, is_estimated, notes,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004740',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 NULL,
 '2025-10-01', '2025-12-31', 'water_liters', 15000.00, 'liters',
 'irrigation', TRUE,
 'Estimated water use for Q4 2025 based on irrigation_program target of 500L/week x 30 weeks.',
 'published', 'pilot_seed', 'adelphi-resource-water-q4',
 '{"record_type":"resource_consumption","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004741',
 'a0000000-0000-0000-0000-000000000001',
 NULL, NULL,
 '2025-10-01', '2025-12-31', 'labor_hours', 320.00, 'hours',
 'all_operations', FALSE,
 'Total labor across planting, weeding, irrigation, spraying, and harvesting for Q4 2025.',
 'published', 'pilot_seed', 'adelphi-resource-labor-q4',
 '{"record_type":"resource_consumption","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004742',
 'a0000000-0000-0000-0000-000000000001',
 NULL, NULL,
 '2026-01-01', '2026-03-31', 'energy_kwh', 45.00, 'kwh',
 'pumping_station', TRUE,
 'Estimated energy for water pumping Q1 2026. Solar-powered pump with battery backup.',
 'published', 'pilot_seed', 'adelphi-resource-energy-q1',
 '{"record_type":"resource_consumption","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    quantity = EXCLUDED.quantity,
    unit = EXCLUDED.unit,
    is_estimated = EXCLUDED.is_estimated,
    updated_at = NOW();

-- Adelphi pilot: pest dynamics model run
INSERT INTO ecological_model_run (
    id, location_id, zone_id, model_name, model_type, run_date,
    input_parameters, output_predictions, confidence_level,
    calculation_version, notes, status,
    source_system, source_id, source_raw
) VALUES (
 'a0000000-0000-0000-0000-000000004750',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'Adelphi Pest Dynamics Model',
 'pest_dynamics',
 '2026-03-10',
 '{
    "baseline_pest_incidence": 12,
    "predator_release_count": 200,
    "predator_species": "Hippodamia convergens",
    "target_pest": "Aphis gossypii",
    "temperature_c": 27.5,
    "humidity_pct": 72.0,
    "area_m2": 2500,
    "season": "wet"
}'::jsonb,
 '{
    "projected_pest_reduction_pct": 68.0,
    "projected_outbreak_probability_pct": 15.0,
    "predator_retention_pct": 72.5,
    "recommended_release_density_per_m2": 0.08,
    "optimal_release_window": "early_wet_season",
    "confidence_interval_low_pct": 55.0,
    "confidence_interval_high_pct": 80.0
}'::jsonb,
 65.0,
 'v2026.03',
 'Pest dynamics model for Adelphi syntropic plot. Lady beetle release against aphid outbreak. Projected 68% pest reduction.',
 'published',
 'pilot_seed', 'adelphi-model-pest-dynamics',
 '{"record_type":"ecological_model_run","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    model_name = EXCLUDED.model_name,
    input_parameters = EXCLUDED.input_parameters,
    output_predictions = EXCLUDED.output_predictions,
    updated_at = NOW();
