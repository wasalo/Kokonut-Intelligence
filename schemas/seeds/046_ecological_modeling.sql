-- ============================================================
-- 046_ecological_modeling.sql — Reference data: metrics, dashboards, trophic seed, Adelphi interactions
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('ecological_interaction_count', 'Ecological Interaction Count', 'Number of documented ecological interactions per location.', 'count(ecological_interaction where status in verified/published)', ARRAY['ecological_interaction'], 'Use published interaction records with evidence_maturity >= 3.', 'Exclude draft or rejected interactions.', 'count', 'integer', 'Ecology Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['ecological_modeling', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('trophic_balance_index', 'Trophic Balance Index', 'Ratio of mutualistic to competitive interactions per location.', 'mutualism_count / (mutualism_count + competition_count)', ARRAY['ecological_interaction'], 'Use published interaction records with verified interaction_type.', 'Exclude records without interaction_type classification.', 'ratio', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["0 <= value <= 1", "total_count > 0"]'::jsonb, ARRAY['ecological_modeling', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('energy_flow_efficiency_pct', 'Energy Flow Efficiency %', 'Average biomass conversion efficiency across trophic transfers.', 'avg(conversion_efficiency_pct) from energy_flow_measurement', ARRAY['energy_flow_measurement'], 'Use published energy flow records with valid efficiency percentages.', 'Exclude records without measured efficiency.', 'percentage', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['ecological_modeling', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('population_stability_index', 'Population Stability Index', 'Coefficient of variation of species population counts over time.', 'stddev(population_count) / avg(population_count)', ARRAY['population_dynamics_record'], 'Use published population records with 3+ data points per species.', 'Exclude species with fewer than 3 observations.', 'index', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['ecological_modeling', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
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

INSERT INTO dashboard_dataset (
    id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata
) VALUES
('a0000000-0000-0000-0000-000000004601', 'Ecological Interactions', 'Public-safe ecological interaction network for syntropic farm analysis.', 'ecological_interaction', NULL, 'dashboards/metabase/sql/62_ecological_interactions.sql', 1440, 'published', '{"owner":"ecology_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004602', 'Trophic Pyramid', 'Public-safe trophic level balance and energy flow visualization.', 'trophic_pyramid', NULL, 'dashboards/metabase/sql/63_trophic_pyramid.sql', 1440, 'published', '{"owner":"ecology_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Trophic level classifications for existing species observations
UPDATE species_observation SET trophic_level = 'producer', population_density_per_m2 = NULL
WHERE species_name IN ('Cocos nucifera', 'Passiflora edulis', 'Canavalia ensiformis', 'Inga edulis', 'Mucuna pruriens', 'Helianthus annuus')
  AND trophic_level IS NULL;

UPDATE species_observation SET trophic_level = 'primary_consumer', population_density_per_m2 = 0.5
WHERE species_name = 'Apis mellifera' AND trophic_level IS NULL;

UPDATE species_observation SET trophic_level = 'primary_consumer', population_density_per_m2 = 0.1
WHERE species_name = 'Gallus gallus domesticus' AND trophic_level IS NULL;

UPDATE species_observation SET trophic_level = 'secondary_consumer', population_density_per_m2 = 0.02
WHERE species_name IN ('Passer domesticus', 'Turdoides striata') AND trophic_level IS NULL;

-- Syntropic strata layer classifications for existing farm zones
UPDATE farm_zone SET strata_layer = 'canopy' WHERE zone_key = 'syntropic-plot' AND strata_layer IS NULL;
UPDATE farm_zone SET strata_layer = 'canopy' WHERE zone_key = 'agroforestry' AND strata_layer IS NULL;
UPDATE farm_zone SET strata_layer = 'decomposer' WHERE zone_key = 'biofactory' AND strata_layer IS NULL;
UPDATE farm_zone SET strata_layer = 'primary_consumer' WHERE zone_key = 'poultry' AND strata_layer IS NULL;

-- Adelphi ecological interactions (pilot examples)
INSERT INTO ecological_interaction (
    id, location_id, zone_id,
    species_a_name, species_a_common, species_a_trophic,
    species_b_name, species_b_common, species_b_trophic,
    interaction_type, interaction_strength, description,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004610',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'Inga edulis', 'Ice cream bean', 'producer',
 'Passiflora edulis', 'Passion fruit', 'producer',
 'facilitation', 0.80,
 'Inga edulis provides nitrogen fixation and shade for passion fruit vines. N-fixing root nodules enrich soil nitrogen available to companion crops.',
 'published', 'pilot_seed', 'adelphi-interaction-inga-passionfruit',
 '{"record_type":"ecological_interaction","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004611',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'Canavalia ensiformis', 'Jack bean', 'producer',
 'Cocos nucifera', 'Coconut palm', 'producer',
 'mutualism', 0.60,
 'Jack bean fixes atmospheric N in root nodules, enriching soil for coconut root zone. Coconut canopy provides partial shade that benefits jack bean growth.',
 'published', 'pilot_seed', 'adelphi-interaction-jackbean-coconut',
 '{"record_type":"ecological_interaction","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004612',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'Apis mellifera', 'Honey bee', 'primary_consumer',
 'Passiflora edulis', 'Passion fruit', 'producer',
 'mutualism', 0.90,
 'Honey bees pollinate passion fruit flowers, directly increasing fruit set and yield. Passion fruit provides nectar and pollen resources.',
 'published', 'pilot_seed', 'adelphi-interaction-bee-passionfruit',
 '{"record_type":"ecological_interaction","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004613',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'Passer domesticus', 'House sparrow', 'secondary_consumer',
 'Apis mellifera', 'Honey bee', 'primary_consumer',
 'predation', 0.30,
 'House sparrows occasionally prey on honey bees, particularly foragers. Predation pressure is low but measurable.',
 'published', 'pilot_seed', 'adelphi-interaction-sparrow-bee',
 '{"record_type":"ecological_interaction","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004614',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'Gallus gallus domesticus', 'Chicken', 'primary_consumer',
 'Cocos nucifera', 'Coconut palm', 'producer',
 'mutualism', 0.50,
 'Free-range chickens consume fallen coconut fruit and insects, reducing pest pressure. Chicken manure provides NPK fertilizer to coconut root zone.',
 'published', 'pilot_seed', 'adelphi-interaction-chicken-coconut',
 '{"record_type":"ecological_interaction","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    species_a_name = EXCLUDED.species_a_name,
    species_b_name = EXCLUDED.species_b_name,
    interaction_type = EXCLUDED.interaction_type,
    interaction_strength = EXCLUDED.interaction_strength,
    description = EXCLUDED.description,
    updated_at = NOW();

-- Adelphi energy flow measurements (pilot examples)
INSERT INTO energy_flow_measurement (
    id, location_id, zone_id, measurement_date,
    from_trophic_level, to_trophic_level,
    biomass_transferred_kg, biomass_source_kg, conversion_efficiency_pct,
    measurement_method, period_start, period_end,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004620',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 '2026-03-10',
 'producer', 'primary_consumer',
 25.00, 1500.00, 1.67,
 'estimation', '2025-10-01', '2026-03-10',
 'published', 'pilot_seed', 'adelphi-energy-producer-consumer',
 '{"record_type":"energy_flow_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004621',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 '2026-03-10',
 'producer', 'decomposer',
 180.00, 1500.00, 12.00,
 'estimation', '2025-10-01', '2026-03-10',
 'published', 'pilot_seed', 'adelphi-energy-producer-decomposer',
 '{"record_type":"energy_flow_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004622',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 '2026-03-10',
 'primary_consumer', 'secondary_consumer',
 0.80, 25.00, 3.20,
 'estimation', '2025-10-01', '2026-03-10',
 'published', 'pilot_seed', 'adelphi-energy-consumer-predator',
 '{"record_type":"energy_flow_measurement","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    from_trophic_level = EXCLUDED.from_trophic_level,
    to_trophic_level = EXCLUDED.to_trophic_level,
    biomass_transferred_kg = EXCLUDED.biomass_transferred_kg,
    conversion_efficiency_pct = EXCLUDED.conversion_efficiency_pct,
    updated_at = NOW();

-- Adelphi population dynamics records (pilot examples)
INSERT INTO population_dynamics_record (
    id, location_id, plot_id, zone_id,
    species_name, species_common_name, trophic_level,
    record_date, population_count, population_density_per_m2,
    carrying_capacity_estimate, growth_rate_estimate, method,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004630',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 'Apis mellifera', 'Honey bee', 'primary_consumer',
 '2025-10-10', 120, 0.48,
 500, 0.05, 'visual',
 'published', 'pilot_seed', 'adelphi-pop-bee-baseline',
 '{"record_type":"population_dynamics_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004631',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 'Apis mellifera', 'Honey bee', 'primary_consumer',
 '2026-03-10', 176, 0.70,
 500, 0.08, 'visual',
 'published', 'pilot_seed', 'adelphi-pop-bee-followup',
 '{"record_type":"population_dynamics_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004632',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 'Passer domesticus', 'House sparrow', 'secondary_consumer',
 '2025-10-10', 8, 0.032,
 50, 0.02, 'visual',
 'published', 'pilot_seed', 'adelphi-pop-sparrow-baseline',
 '{"record_type":"population_dynamics_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004633',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 'Passer domesticus', 'House sparrow', 'secondary_consumer',
 '2026-03-10', 12, 0.048,
 50, 0.07, 'visual',
 'published', 'pilot_seed', 'adelphi-pop-sparrow-followup',
 '{"record_type":"population_dynamics_record","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    species_name = EXCLUDED.species_name,
    population_count = EXCLUDED.population_count,
    population_density_per_m2 = EXCLUDED.population_density_per_m2,
    updated_at = NOW();

-- Adelphi ecological model run (nutrient cycling pilot)
INSERT INTO ecological_model_run (
    id, location_id, zone_id, model_name, model_type, run_date,
    input_parameters, output_predictions, confidence_level,
    calculation_version, notes, status,
    source_system, source_id, source_raw
) VALUES (
 'a0000000-0000-0000-0000-000000004640',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'Adelphi Nutrient Cycling Model',
 'nutrient_cycling',
 '2026-03-10',
 '{
    "initial_soil_nitrogen_ppm": 35.0,
    "tree_canopy_growth_rate_m_per_year": 0.5,
    "leaf_litter_rate_kg_per_day": 5.0,
    "decomposition_rate_pct_per_month": 15.0,
    "n_fixer_species": "Inga edulis",
    "companion_crop": "Passiflora edulis",
    "area_m2": 7838,
    "rainfall_mm": 120,
    "temperature_c": 28.5
}'::jsonb,
 '{
    "projected_soil_nitrogen_3_seasons_ppm": 42.0,
    "nitrogen_increase_pct": 20.0,
    "projected_vegetation_biomass_gain_pct": 15.0,
    "recommended_intercrop_ratio": "1:3",
    "leaf_litter_contribution_kg_per_year": 1825.0,
    "n_fixation_contribution_kg_per_year": 45.0
}'::jsonb,
 75.0,
 'v2026.03',
 'Nutrient cycling model for Adelphi syntropic plot. N-fixer Inga edulis + passion fruit intercrop. Projected 20% soil N increase over 3 seasons.',
 'published',
 'pilot_seed', 'adelphi-model-nutrient-cycling',
 '{"record_type":"ecological_model_run","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    model_name = EXCLUDED.model_name,
    input_parameters = EXCLUDED.input_parameters,
    output_predictions = EXCLUDED.output_predictions,
    updated_at = NOW();
