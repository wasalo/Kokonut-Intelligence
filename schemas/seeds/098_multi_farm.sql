-- ============================================================
-- 098_multi_farm.sql — Seed data for Kokonut Genesis
-- ============================================================

-- Second farm: Kokonut Genesis, Barahona, Dominican Republic
INSERT INTO location (id, name, status, centroid, metadata) VALUES
('a0000000-0000-0000-0000-000000000002', 'Kokonut Genesis', 'active',
 ST_SetSRID(ST_MakePoint(-71.1896, 18.2918), 4326),
 '{"region":"Caribbean","country":"Dominican Republic","province":"Barahona","coordinates_source":"manual"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, status = EXCLUDED.status;

-- Farm record
INSERT INTO farm (id, location_id, name, farm_type, status) VALUES
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 'Kokonut Genesis Farm', 'coconut', 'active')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;

-- Farm registry record
INSERT INTO farm_registry_record (
    id, farm_id, location_id, registry_slug, project_date,
    forecasted_budget, land_size_m2,
    governance_mechanism, token_allocation,
    public_goods_allocation_pct,
    project_summary, local_problem, proposed_solution,
    status
) VALUES (
    'a0000000-0000-0000-0000-000000000022',
    'a0000000-0000-0000-0000-000000000012',
    'a0000000-0000-0000-0000-000000000002',
    'kokonut-genesis',
    '2026-03-01',
    45000.00,
    20000.0000,
    'moloch_dao',
    'Genesis DAO shares backed by coconut trees',
    10.000,
    'Kokonut Genesis is the second farm in the Kokonut Network, located in Barahona, Dominican Republic. Specializing in coconut cultivation with regenerative practices.',
    'Limited access to capital for smallholder coconut farmers in Barahona region',
    'Blockchain-enabled cooperative model connecting Web3 capital with real-world farming',
    'published'
) ON CONFLICT (id) DO UPDATE SET
    project_summary = EXCLUDED.project_summary,
    status = EXCLUDED.status;

-- Governance token (external, example placeholder)
INSERT INTO governance_token (chain, contract_address, symbol, name, decimals, deployment_mode, status) VALUES
('polygon', '0x0000000000000000000000000000000000000001', 'KKN', 'Kokonut Network Token', 18, 'external', 'active')
ON CONFLICT (chain, contract_address) DO UPDATE SET symbol = EXCLUDED.symbol;

-- Onboarding workflow steps for Genesis
INSERT INTO farm_onboarding_workflow (farm_id, location_id, step_order, step_name, step_type, status) VALUES
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 1, 'Land Assessment', 'land_assessment', 'completed'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 2, 'Community Engagement', 'community_engagement', 'completed'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 3, 'Template Selection', 'template_selection', 'completed'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 4, 'Farm Specification', 'farm_specification', 'in_progress'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 5, 'Zone Setup', 'zone_setup', 'pending'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 6, 'Governance Setup', 'governance_setup', 'pending'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 7, 'Token Binding', 'token_binding', 'pending'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 8, 'Soil Baseline', 'soil_baseline', 'pending'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 9, 'Planting', 'planting', 'pending'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 10, 'Monitoring Setup', 'monitoring_setup', 'pending'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 11, 'MRV Setup', 'mrve_setup', 'pending'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 12, 'Certification', 'certification', 'pending'),
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002', 13, 'Go Live', 'go_live', 'pending')
ON CONFLICT (farm_id, step_order) DO UPDATE SET status = EXCLUDED.status;

-- Farm template instance
INSERT INTO farm_template_instance (farm_id, location_id, template_id, template_version, customizations, status) VALUES
('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002',
 (SELECT id FROM farm_template WHERE template_name = 'Coconut Syntropic' LIMIT 1),
 '1.0', '{"climate_zone": "tropical", "primary_crop": "coconut", "secondary_crops": ["cacao", "banana"]}'::jsonb, 'applied')
ON CONFLICT DO NOTHING;
