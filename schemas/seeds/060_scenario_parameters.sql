-- ============================================================
-- 060_scenario_parameters.sql — Seeds: Default parameters for Adelphi scenarios
-- ============================================================

-- Baseline scenario parameters
INSERT INTO scenario_parameter (
    scenario_id, parameter_key, parameter_category, parameter_name, description,
    unit, base_value, worst_value, best_value, distribution, std_deviation,
    min_bound, max_bound, source_system, source_id, source_raw
) VALUES
-- Yield parameters
('a0000000-0000-0000-0000-000000000080', 'loss_rate', 'yield', 'Post-Harvest Loss Rate', 'Percentage of harvest lost post-production',
 'ratio', 0.05, 0.15, 0.02, 'triangular', 0.03, 0.0, 0.30,
 'pilot_seed', 'baseline-loss-rate', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'drought_yield_impact', 'yield', 'Drought Yield Impact', 'Yield reduction during drought conditions',
 'ratio', 0.00, 0.30, 0.00, 'triangular', 0.10, 0.0, 0.50,
 'pilot_seed', 'baseline-drought-impact', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'pest_disease_loss', 'yield', 'Pest & Disease Loss', 'Yield loss from pest and disease pressure',
 'ratio', 0.03, 0.10, 0.01, 'triangular', 0.02, 0.0, 0.20,
 'pilot_seed', 'baseline-pest-loss', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'yield_improvement', 'yield', 'Annual Yield Improvement', 'Year-over-year yield improvement rate',
 'ratio', 0.05, 0.02, 0.12, 'triangular', 0.02, 0.0, 0.20,
 'pilot_seed', 'baseline-yield-improvement', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
-- Price parameters
('a0000000-0000-0000-0000-000000000080', 'maize_price', 'price', 'Maize Price', 'Maize market price per tonne',
 'usd_per_tonne', 280, 200, 350, 'normal', 30, 150, 400,
 'pilot_seed', 'baseline-maize-price', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'cassava_price', 'price', 'Cassava Price', 'Cassava market price per tonne',
 'usd_per_tonne', 180, 130, 230, 'normal', 20, 100, 280,
 'pilot_seed', 'baseline-cassava-price', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'beans_price', 'price', 'Beans Price', 'Beans market price per tonne',
 'usd_per_tonne', 650, 450, 800, 'normal', 60, 350, 900,
 'pilot_seed', 'baseline-beans-price', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'sweet_potato_price', 'price', 'Sweet Potato Price', 'Sweet potato market price per tonne',
 'usd_per_tonne', 220, 160, 280, 'normal', 25, 120, 320,
 'pilot_seed', 'baseline-sweet-potato-price', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
-- Cost parameters
('a0000000-0000-0000-0000-000000000080', 'fertilizer_cost_inflation', 'cost', 'Fertilizer Cost Inflation', 'Annual fertilizer cost change rate',
 'ratio', 0.05, 0.15, 0.02, 'triangular', 0.03, -0.05, 0.30,
 'pilot_seed', 'baseline-fertilizer-inflation', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'labor_cost_inflation', 'cost', 'Labor Cost Inflation', 'Annual labor cost change rate',
 'ratio', 0.05, 0.10, 0.03, 'triangular', 0.02, 0.0, 0.20,
 'pilot_seed', 'baseline-labor-inflation', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'transport_cost_inflation', 'cost', 'Transport Cost Inflation', 'Annual transport cost change rate',
 'ratio', 0.05, 0.12, 0.03, 'triangular', 0.02, 0.0, 0.25,
 'pilot_seed', 'baseline-transport-inflation', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'seed_cost_inflation', 'cost', 'Seed Cost Inflation', 'Annual seed cost change rate',
 'ratio', 0.05, 0.08, 0.02, 'triangular', 0.01, 0.0, 0.15,
 'pilot_seed', 'baseline-seed-inflation', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
-- Weather parameters
('a0000000-0000-0000-0000-000000000080', 'drought_probability', 'weather', 'Drought Probability', 'Annual probability of drought conditions',
 'ratio', 0.10, 0.25, 0.05, 'triangular', 0.05, 0.0, 0.50,
 'pilot_seed', 'baseline-drought-prob', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'flood_probability', 'weather', 'Flood Probability', 'Annual probability of flood conditions',
 'ratio', 0.05, 0.15, 0.02, 'triangular', 0.03, 0.0, 0.30,
 'pilot_seed', 'baseline-flood-prob', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
-- Ecological parameters
('a0000000-0000-0000-0000-000000000080', 'carbon_sequestration_rate', 'ecological', 'Carbon Sequestration Rate', 'Annual carbon sequestration per hectare',
 'tonnes_per_ha_yr', 8.5, 5.0, 12.0, 'triangular', 1.5, 2.0, 15.0,
 'pilot_seed', 'baseline-carbon-rate', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'biodiversity_credit_price', 'ecological', 'Biodiversity Credit Price', 'Price per species credit',
 'usd_per_credit', 50, 25, 100, 'normal', 15, 10, 150,
 'pilot_seed', 'baseline-biodiversity-price', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
-- Governance parameters
('a0000000-0000-0000-0000-000000000080', 'public_goods_allocation_pct', 'governance', 'Public Goods Allocation', 'Percentage of revenue allocated to public goods',
 'ratio', 0.10, 0.15, 0.05, 'triangular', 0.02, 0.0, 0.30,
 'pilot_seed', 'baseline-public-goods', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000080', 'retention_rate_pct', 'governance', 'Retention Rate', 'Percentage of revenue retained by farm',
 'ratio', 0.20, 0.10, 0.35, 'triangular', 0.05, 0.0, 0.50,
 'pilot_seed', 'baseline-retention', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb)
ON CONFLICT (scenario_id, parameter_key) DO UPDATE SET
    base_value = EXCLUDED.base_value,
    worst_value = EXCLUDED.worst_value,
    best_value = EXCLUDED.best_value,
    updated_at = NOW();

-- Optimistic scenario parameters (adjusted for best case)
INSERT INTO scenario_parameter (
    scenario_id, parameter_key, parameter_category, parameter_name, description,
    unit, base_value, worst_value, best_value, distribution, std_deviation,
    min_bound, max_bound, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000081', 'loss_rate', 'yield', 'Post-Harvest Loss Rate', 'Percentage of harvest lost post-production',
 'ratio', 0.03, 0.10, 0.01, 'triangular', 0.02, 0.0, 0.20,
 'pilot_seed', 'optimistic-loss-rate', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000081', 'drought_yield_impact', 'yield', 'Drought Yield Impact', 'Yield reduction during drought conditions',
 'ratio', 0.00, 0.20, 0.00, 'triangular', 0.05, 0.0, 0.40,
 'pilot_seed', 'optimistic-drought-impact', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000081', 'maize_price', 'price', 'Maize Price', 'Maize market price per tonne',
 'usd_per_tonne', 320, 250, 400, 'normal', 25, 200, 450,
 'pilot_seed', 'optimistic-maize-price', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000081', 'fertilizer_cost_inflation', 'cost', 'Fertilizer Cost Inflation', 'Annual fertilizer cost change rate',
 'ratio', 0.02, 0.08, 0.00, 'triangular', 0.02, -0.05, 0.15,
 'pilot_seed', 'optimistic-fertilizer-inflation', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000081', 'drought_probability', 'weather', 'Drought Probability', 'Annual probability of drought conditions',
 'ratio', 0.05, 0.15, 0.02, 'triangular', 0.03, 0.0, 0.30,
 'pilot_seed', 'optimistic-drought-prob', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000081', 'carbon_sequestration_rate', 'ecological', 'Carbon Sequestration Rate', 'Annual carbon sequestration per hectare',
 'tonnes_per_ha_yr', 12.0, 8.0, 15.0, 'triangular', 1.5, 5.0, 18.0,
 'pilot_seed', 'optimistic-carbon-rate', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000081', 'public_goods_allocation_pct', 'governance', 'Public Goods Allocation', 'Percentage of revenue allocated to public goods',
 'ratio', 0.05, 0.10, 0.03, 'triangular', 0.01, 0.0, 0.20,
 'pilot_seed', 'optimistic-public-goods', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000081', 'retention_rate_pct', 'governance', 'Retention Rate', 'Percentage of revenue retained by farm',
 'ratio', 0.35, 0.20, 0.45, 'triangular', 0.05, 0.10, 0.60,
 'pilot_seed', 'optimistic-retention', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb)
ON CONFLICT (scenario_id, parameter_key) DO UPDATE SET
    base_value = EXCLUDED.base_value,
    worst_value = EXCLUDED.worst_value,
    best_value = EXCLUDED.best_value,
    updated_at = NOW();

-- Conservative scenario parameters (adjusted for worst case)
INSERT INTO scenario_parameter (
    scenario_id, parameter_key, parameter_category, parameter_name, description,
    unit, base_value, worst_value, best_value, distribution, std_deviation,
    min_bound, max_bound, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000082', 'loss_rate', 'yield', 'Post-Harvest Loss Rate', 'Percentage of harvest lost post-production',
 'ratio', 0.10, 0.25, 0.05, 'triangular', 0.05, 0.0, 0.40,
 'pilot_seed', 'conservative-loss-rate', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'drought_yield_impact', 'yield', 'Drought Yield Impact', 'Yield reduction during drought conditions',
 'ratio', 0.20, 0.40, 0.05, 'triangular', 0.10, 0.0, 0.60,
 'pilot_seed', 'conservative-drought-impact', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'pest_disease_loss', 'yield', 'Pest & Disease Loss', 'Yield loss from pest and disease pressure',
 'ratio', 0.08, 0.18, 0.03, 'triangular', 0.04, 0.0, 0.30,
 'pilot_seed', 'conservative-pest-loss', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'maize_price', 'price', 'Maize Price', 'Maize market price per tonne',
 'usd_per_tonne', 250, 180, 300, 'normal', 30, 140, 350,
 'pilot_seed', 'conservative-maize-price', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'fertilizer_cost_inflation', 'cost', 'Fertilizer Cost Inflation', 'Annual fertilizer cost change rate',
 'ratio', 0.10, 0.25, 0.05, 'triangular', 0.04, 0.0, 0.40,
 'pilot_seed', 'conservative-fertilizer-inflation', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'labor_cost_inflation', 'cost', 'Labor Cost Inflation', 'Annual labor cost change rate',
 'ratio', 0.08, 0.15, 0.05, 'triangular', 0.02, 0.0, 0.25,
 'pilot_seed', 'conservative-labor-inflation', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'drought_probability', 'weather', 'Drought Probability', 'Annual probability of drought conditions',
 'ratio', 0.25, 0.40, 0.10, 'triangular', 0.08, 0.0, 0.60,
 'pilot_seed', 'conservative-drought-prob', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'carbon_sequestration_rate', 'ecological', 'Carbon Sequestration Rate', 'Annual carbon sequestration per hectare',
 'tonnes_per_ha_yr', 5.0, 2.0, 8.0, 'triangular', 1.5, 1.0, 10.0,
 'pilot_seed', 'conservative-carbon-rate', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'public_goods_allocation_pct', 'governance', 'Public Goods Allocation', 'Percentage of revenue allocated to public goods',
 'ratio', 0.15, 0.20, 0.10, 'triangular', 0.02, 0.05, 0.30,
 'pilot_seed', 'conservative-public-goods', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000082', 'retention_rate_pct', 'governance', 'Retention Rate', 'Percentage of revenue retained by farm',
 'ratio', 0.10, 0.05, 0.20, 'triangular', 0.03, 0.0, 0.30,
 'pilot_seed', 'conservative-retention', '{"record_type":"scenario_parameter","privacy":"public_summary"}'::jsonb)
ON CONFLICT (scenario_id, parameter_key) DO UPDATE SET
    base_value = EXCLUDED.base_value,
    worst_value = EXCLUDED.worst_value,
    best_value = EXCLUDED.best_value,
    updated_at = NOW();
