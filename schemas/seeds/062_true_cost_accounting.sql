-- ============================================================
-- 062_true_cost_accounting.sql — Seeds: Adelphi pilot data
-- ============================================================

-- ============================================================================
-- PHASE 1: HIDDEN COSTS (Adelphi)
-- ============================================================================

INSERT INTO hidden_cost_observation (
    id, location_id, observation_date, cost_category, cost_subcategory,
    description, affected_population, monetary_estimate_usd, valuation_method,
    uncertainty_level, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000620',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'environmental', 'soil_degradation',
 'Pre-transition soil organic matter loss from conventional practices on adjacent plot. Estimated 0.3% SOM decline over 5 years prior to organic transition.',
 'Farm ecosystem and downstream water users', 450.00, 'replacement_cost',
 'medium', 'published', 'pilot_seed', 'adelphi-hidden-soil',
 '{"record_type":"hidden_cost_observation","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000621',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'environmental', 'biodiversity_loss',
 'Reduced pollinator habitat before establishing agroforestry corridor. Native bee populations declined during transition period.',
 'Farm ecosystem and surrounding pollinator networks', 320.00, 'benefit_transfer',
 'high', 'published', 'pilot_seed', 'adelphi-hidden-biodiversity',
 '{"record_type":"hidden_cost_observation","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000622',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'health', 'pesticide_exposure',
 'Historical pesticide use on adjacent conventional farm causing drift exposure to organic boundary. Estimated health risk to farm workers.',
 'Farm workers and nearby residents', 180.00, 'cost_avoidance',
 'medium', 'published', 'pilot_seed', 'adelphi-hidden-health',
 '{"record_type":"hidden_cost_observation","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000623',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'social', 'cultural_erosion',
 'Loss of traditional farming knowledge during transition from conventional to syntropic methods. Elder knowledge holders not yet fully integrated.',
 'Farm community and elder knowledge keepers', 150.00, 'replacement_cost',
 'high', 'published', 'pilot_seed', 'adelphi-hidden-cultural',
 '{"record_type":"hidden_cost_observation","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    monetary_estimate_usd = EXCLUDED.monetary_estimate_usd,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- PHASE 1: NATURAL CAPITAL VALUATION (Adelphi)
-- ============================================================================

INSERT INTO natural_capital_valuation (
    id, location_id, valuation_date, capital_type, service_description,
    quantity, unit, price_per_unit_usd, valuation_method,
    status, source_system, source_id, source_raw
) VALUES
-- Carbon sequestration
('a0000000-0000-0000-0000-000000000630',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'carbon', 'Above-ground and below-ground carbon sequestration from coconut palms and agroforestry corridor',
 57.53, 'tonnes_co2e', 25.00, 'market_price',
 'published', 'pilot_seed', 'adelphi-ncv-carbon',
 '{"record_type":"natural_capital_valuation","privacy":"public_summary"}'::jsonb),
-- Biodiversity
('a0000000-0000-0000-0000-000000000631',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'biodiversity', 'Species diversity across farm ecosystem including birds, insects, and companion plants',
 37, 'species_count', 35.00, 'benefit_transfer',
 'published', 'pilot_seed', 'adelphi-ncv-biodiversity',
 '{"record_type":"natural_capital_valuation","privacy":"public_summary"}'::jsonb),
-- Water stewardship
('a0000000-0000-0000-0000-000000000632',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'water', 'Rainwater harvesting and efficient irrigation reducing downstream water extraction',
 50000, 'liters', 0.002, 'replacement_cost',
 'published', 'pilot_seed', 'adelphi-ncv-water',
 '{"record_type":"natural_capital_valuation","privacy":"public_summary"}'::jsonb),
-- Soil health
('a0000000-0000-0000-0000-000000000633',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'soil', 'Soil organic matter improvement from compost and biochar application across 3 plots',
 3.2, 'percent_som_increase', 500.00, 'benefit_transfer',
 'published', 'pilot_seed', 'adelphi-ncv-soil',
 '{"record_type":"natural_capital_valuation","privacy":"public_summary"}'::jsonb),
-- Pollination
('a0000000-0000-0000-0000-000000000634',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'pollination', 'Pollinator habitat support from agroforestry corridor and companion planting',
 22, 'pollinator_species', 15.00, 'benefit_transfer',
 'published', 'pilot_seed', 'adelphi-ncv-pollination',
 '{"record_type":"natural_capital_valuation","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    quantity = EXCLUDED.quantity,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- PHASE 2: SOCIAL IMPACT VALUATION (Adelphi)
-- ============================================================================

INSERT INTO social_impact_valuation (
    id, location_id, valuation_date, impact_category, impact_description,
    beneficiaries_count, monetary_value_usd, valuation_method,
    status, source_system, source_id, source_raw
) VALUES
-- Training
('a0000000-0000-0000-0000-000000000640',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'training', 'Soil management, pest management, and financial literacy training for community members. 4 sessions delivered with average 64% improvement.',
 12, 2400.00, 'replacement_cost',
 'published', 'pilot_seed', 'adelphi-siv-training',
 '{"record_type":"social_impact_valuation","privacy":"public_summary"}'::jsonb),
-- Governance
('a0000000-0000-0000-0000-000000000641',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'governance', 'Community governance participation through DAO proposals and council meetings. Enhanced decision-making capacity.',
 15, 1800.00, 'benefit_transfer',
 'published', 'pilot_seed', 'adelphi-siv-governance',
 '{"record_type":"social_impact_valuation","privacy":"public_summary"}'::jsonb),
-- Cultural preservation
('a0000000-0000-0000-0000-000000000642',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'cultural_preservation', 'Integration of traditional farming knowledge with syntropic methods. Heritage coconut varieties maintained.',
 8, 1200.00, 'replacement_cost',
 'published', 'pilot_seed', 'adelphi-siv-culture',
 '{"record_type":"social_impact_valuation","privacy":"public_summary"}'::jsonb),
-- Health
('a0000000-0000-0000-0000-000000000643',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'health', 'Reduced pesticide exposure through organic transition. Improved food safety for farm workers and community.',
 20, 800.00, 'cost_avoidance',
 'published', 'pilot_seed', 'adelphi-siv-health',
 '{"record_type":"social_impact_valuation","privacy":"public_summary"}'::jsonb),
-- Community
('a0000000-0000-0000-0000-000000000644',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'community', 'Public goods allocation supporting community infrastructure and shared resources.',
 25, 1500.00, 'benefit_transfer',
 'published', 'pilot_seed', 'adelphi-siv-community',
 '{"record_type":"social_impact_valuation","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    monetary_value_usd = EXCLUDED.monetary_value_usd,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- PHASE 2: LIVING WAGE BENCHMARK (Adelphi)
-- ============================================================================

INSERT INTO living_wage_benchmark (
    id, location_id, benchmark_date, country,
    living_wage_hourly_usd, minimum_wage_hourly_usd, source, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000650',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'Dominican Republic', 2.50, 1.25,
 'Global Living Wage Coalition / Anker methodology', 'active',
 'pilot_seed', 'adelphi-living-wage-dr',
 '{"record_type":"living_wage_benchmark","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    living_wage_hourly_usd = EXCLUDED.living_wage_hourly_usd,
    updated_at = NOW();

-- ============================================================================
-- PHASE 3: LCA ASSESSMENT (Adelphi — coconut production)
-- ============================================================================

INSERT INTO lca_assessment (
    id, location_id, crop_cycle_id, assessment_date, lifecycle_stage,
    input_type, quantity, unit,
    carbon_footprint_kg_co2e, water_footprint_liters, energy_footprint_kwh, waste_generated_kg,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000660',
 'a0000000-0000-0000-0000-000000000001', NULL, '2025-12-31',
 'input_production', 'Compost (on-farm produced)', 500.0, 'kg',
 25.0, 0.0, 5.0, 0.0,
 'published', 'pilot_seed', 'adelphi-lca-compost',
 '{"record_type":"lca_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000661',
 'a0000000-0000-0000-0000-000000000001', NULL, '2025-12-31',
 'cultivation', 'Coconut palm maintenance', 1.57, 'hectares',
 150.0, 25000.0, 50.0, 10.0,
 'published', 'pilot_seed', 'adelphi-lca-cultivation',
 '{"record_type":"lca_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000662',
 'a0000000-0000-0000-0000-000000000001', NULL, '2025-12-31',
 'harvest', 'Coconut harvest and collection', 2.5, 'tonnes',
 30.0, 500.0, 10.0, 50.0,
 'published', 'pilot_seed', 'adelphi-lca-harvest',
 '{"record_type":"lca_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000663',
 'a0000000-0000-0000-0000-000000000001', NULL, '2025-12-31',
 'transport', 'Local transport to market', 2.5, 'tonnes',
 45.0, 0.0, 20.0, 0.0,
 'published', 'pilot_seed', 'adelphi-lca-transport',
 '{"record_type":"lca_assessment","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    carbon_footprint_kg_co2e = EXCLUDED.carbon_footprint_kg_co2e,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- PHASE 4: GRI INDICATORS (core mapping)
-- ============================================================================

INSERT INTO gri_indicator (
    gri_code, gri_standard, indicator_name, description,
    platform_metric_key, platform_table, platform_field, data_type, status
) VALUES
('GRI 301-1', 'GRI 301: Materials', 'Materials used by weight or volume', 'Total materials used in production',
 NULL, 'expense_event', 'amount', 'quantitative', 'active'),
('GRI 302-1', 'GRI 302: Energy', 'Energy consumption within the organization', 'Total energy consumption',
 NULL, 'resource_consumption', 'quantity', 'quantitative', 'active'),
('GRI 303-3', 'GRI 303: Water', 'Water withdrawal', 'Total water withdrawal by source',
 NULL, 'water_access', 'capacity_liters', 'quantitative', 'active'),
('GRI 305-1', 'GRI 305: Emissions', 'Direct (Scope 1) GHG emissions', 'Direct greenhouse gas emissions',
 NULL, 'ghg_emissions_inventory', 'total_co2e_kg', 'quantitative', 'active'),
('GRI 305-5', 'GRI 305: Emissions', 'GHG emissions intensity', 'GHG emissions per unit of output',
 NULL, 'climate_impact_summary', 'total_emissions_tonnes_co2e', 'quantitative', 'active'),
('GRI 401-1', 'GRI 401: Employment', 'New employee hires and employee turnover', 'Staff hiring and retention',
 NULL, 'staff', 'is_active', 'quantitative', 'active'),
('GRI 403-1', 'GRI 403: Occupational Health', 'Occupational health and safety management system', 'Worker safety incidents',
 NULL, 'worker_safety_observation', 'incident_type', 'quantitative', 'active'),
('GRI 404-1', 'GRI 404: Training', 'Average hours of training per year', 'Training hours delivered',
 NULL, 'training_session', 'duration_hours', 'quantitative', 'active'),
('GRI 413-1', 'GRI 413: Local Communities', 'Operations with local community engagement', 'Community governance participation',
 NULL, 'community_governance_mechanism', 'decision_method', 'qualitative', 'active'),
('GRI 201-1', 'GRI 201: Economic Performance', 'Direct economic value generated', 'Revenue and value generation',
 NULL, 'revenue_event', 'amount_usd', 'quantitative', 'active')
ON CONFLICT (gri_code) DO UPDATE SET
    indicator_name = EXCLUDED.indicator_name,
    platform_metric_key = EXCLUDED.platform_metric_key,
    updated_at = NOW();

-- ============================================================================
-- PHASE 4: MATERIALITY ASSESSMENT (Adelphi)
-- ============================================================================

INSERT INTO materiality_assessment (
    id, location_id, assessment_date, stakeholder_group, material_topic,
    topic_category, importance_to_stakeholder, importance_to_business, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000670',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'farmers', 'Soil Health & Organic Matter', 'environmental',
 5, 5, 'published',
 'pilot_seed', 'adelphi-materiality-soil',
 '{"record_type":"materiality_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000671',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'workers', 'Fair Wages & Working Conditions', 'social',
 5, 4, 'published',
 'pilot_seed', 'adelphi-materiality-wages',
 '{"record_type":"materiality_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000672',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'community', 'Community Wellbeing & Training', 'social',
 4, 4, 'published',
 'pilot_seed', 'adelphi-materiality-community',
 '{"record_type":"materiality_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000673',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'funders', 'Financial Sustainability & ROI', 'economic',
 4, 5, 'published',
 'pilot_seed', 'adelphi-materiality-financial',
 '{"record_type":"materiality_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000674',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'regulators', 'Organic Certification Compliance', 'governance',
 5, 5, 'published',
 'pilot_seed', 'adelphi-materiality-compliance',
 '{"record_type":"materiality_assessment","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    importance_to_stakeholder = EXCLUDED.importance_to_stakeholder,
    importance_to_business = EXCLUDED.importance_to_business,
    updated_at = NOW();

-- ============================================================================
-- PHASE 5: CAPITAL FLOW OBSERVATIONS (Adelphi)
-- ============================================================================

INSERT INTO capital_flow_observation (
    id, location_id, observation_date, from_capital, to_capital,
    flow_description, flow_value_usd, flow_type,
    status, source_system, source_id, source_raw
) VALUES
-- Financial -> Natural (compost production improves soil)
('a0000000-0000-0000-0000-000000000680',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'financial', 'natural',
 'Investment in compost production and biochar application to improve soil health', 1200.00, 'investment',
 'published', 'pilot_seed', 'adelphi-flow-financial-natural',
 '{"record_type":"capital_flow_observation","privacy":"public_summary"}'::jsonb),
-- Financial -> Human (training investment)
('a0000000-0000-0000-0000-000000000681',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'financial', 'human',
 'Investment in community training programs (soil, pest, financial management)', 800.00, 'investment',
 'published', 'pilot_seed', 'adelphi-flow-financial-human',
 '{"record_type":"capital_flow_observation","privacy":"public_summary"}'::jsonb),
-- Natural -> Financial (carbon credits from sequestration)
('a0000000-0000-0000-0000-000000000682',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'natural', 'financial',
 'Carbon sequestration generating potential carbon credit revenue', 1438.25, 'regeneration',
 'published', 'pilot_seed', 'adelphi-flow-natural-financial',
 '{"record_type":"capital_flow_observation","privacy":"public_summary"}'::jsonb),
-- Human -> Social (knowledge transfer to community)
('a0000000-0000-0000-0000-000000000683',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'human', 'social',
 'Knowledge transfer from trained staff to community members through workshops', 2400.00, 'transfer',
 'published', 'pilot_seed', 'adelphi-flow-human-social',
 '{"record_type":"capital_flow_observation","privacy":"public_summary"}'::jsonb),
-- Natural -> Produced (biomass from coconut production)
('a0000000-0000-0000-0000-000000000684',
 'a0000000-0000-0000-0000-000000000001', '2025-12-31',
 'natural', 'produced',
 'Coconut harvest converting natural capital into produced goods', 9200.00, 'transfer',
 'published', 'pilot_seed', 'adelphi-flow-natural-produced',
 '{"record_type":"capital_flow_observation","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    flow_value_usd = EXCLUDED.flow_value_usd,
    status = EXCLUDED.status,
    updated_at = NOW();
