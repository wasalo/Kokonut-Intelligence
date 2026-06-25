-- ============================================================
-- Seed: Kokonut Adelphi alignment
-- ============================================================

-- This seed runs after legacy pilot rows so reruns converge on the KB-aligned
-- Adelphi state without deleting operational history used by MVP checks.

UPDATE location
SET name = 'Kokonut Adelphi',
    slug = 'kokonut-adelphi',
    description = 'First live Kokonut syntropic farm proof in Sabana Grande de Boya, Monte Plata, Dominican Republic',
    country = 'Dominican Republic',
    region = 'Monte Plata',
    sub_region = 'Sabana Grande de Boya',
    timezone = 'America/Santo_Domingo',
    metadata = COALESCE(metadata, '{}'::jsonb) || '{"source":"kokonut knowledge base","hub_url":"https://hub.kokonut.network/projects/41","proof_stage":"first_live_syntropic_farm","women_led":true,"public_goods_allocation_pct":10}'::jsonb,
    updated_at = NOW()
WHERE id = 'a0000000-0000-0000-0000-000000000001';

UPDATE farm_registry_record
SET registry_slug = 'kokonut-adelphi',
    land_size_m2 = 15725.0000,
    project_location = '{"community":"Gonzalo","municipality":"Sabana Grande de Boya","province":"Monte Plata","country":"Dominican Republic","coordinates":null}'::jsonb,
    source_of_funding = 'Public Nouns #69 funding context, Kokonut DAO pilot allocation, and partner sponsorship seed data',
    revenue_streams = ARRAY['lettuce', 'passion_fruit', 'coconut', 'eggs', 'indian_yam', 'nursery', 'bioinputs'],
    governance_mechanism = 'moloch_dao',
    public_goods_allocation_pct = 10.000,
    project_summary = 'Kokonut Adelphi is the first live Kokonut syntropic farm proof: a women-led, community-first 15,725 m2 farm in Sabana Grande de Boya with 13,838 m2 of agricultural land.',
    local_problem = 'Regenerative farms need comparable operating records, transparent funding paths, and public-good accountability before they can be replicated responsibly.',
    proposed_solution = 'Adelphi combines syntropic production, bioinputs, community operations, MRV-ready ecological tracking, and DAO-linked value flows with a 10% public goods allocation.',
    target_market = ARRAY['local_buyers', 'direct_buyers', 'public_goods_funders', 'partner_sponsors'],
    source_system = 'pilot_seed',
    source_id = 'kokonut-adelphi',
    source_raw = '{"source":"kokonut knowledge base","schema":"common-data-schema-v1","hub_url":"https://hub.kokonut.network/projects/41","total_area_m2":15725,"agricultural_land_m2":13838}'::jsonb,
    status = 'published',
    updated_at = NOW()
WHERE id = 'a0000000-0000-0000-0000-000000000500';

-- Public EAS metadata should point to Celo schemas; legacy Optimism pilot
-- schemas remain only as inactive local-dev history.
UPDATE attestation_schema
SET active = FALSE
WHERE id IN ('a0000000-0000-0000-0000-0000000001a0', 'a0000000-0000-0000-0000-0000000001a1')
  AND chain = 'optimism';

UPDATE attestation_record
SET schema_id = CASE id
        WHEN 'a0000000-0000-0000-0000-0000000001b0' THEN 'a0000000-0000-0000-0000-0000000001e0'::uuid
        WHEN 'a0000000-0000-0000-0000-0000000001b1' THEN 'a0000000-0000-0000-0000-0000000001e3'::uuid
        WHEN 'a0000000-0000-0000-0000-0000000001b2' THEN 'a0000000-0000-0000-0000-0000000001e1'::uuid
        WHEN 'a0000000-0000-0000-0000-0000000001b3' THEN 'a0000000-0000-0000-0000-0000000001e3'::uuid
        ELSE schema_id
    END,
    claim_data = CASE id
        WHEN 'a0000000-0000-0000-0000-0000000001b0' THEN '{"locationId":"a0000000-0000-0000-0000-000000000001","farmId":"a0000000-0000-0000-0000-000000000010","cropType":"Lettuce","activityType":"planting","quantity":0.20,"unit":"hectares","measurementDate":"2025-10-01","payloadCid":"local://sha256/4f24f70db68140c8584b2ad3e8433a260e4f25d7c607b45cbf1dc64ceb9684b6"}'::jsonb
        WHEN 'a0000000-0000-0000-0000-0000000001b1' THEN '{"locationId":"a0000000-0000-0000-0000-000000000001","cropCycleId":"a0000000-0000-0000-0000-000000000040","quantity":4.80,"unit":"tonnes","qualityGrade":"A","harvestDate":"2025-11-12"}'::jsonb
        WHEN 'a0000000-0000-0000-0000-0000000001b2' THEN '{"locationId":"a0000000-0000-0000-0000-000000000001","metric":"syntropic_establishment","value":13838,"unit":"m2","period":"Oct-Dec 2025","payloadCid":"local://sha256/4f24f70db68140c8584b2ad3e8433a260e4f25d7c607b45cbf1dc64ceb9684b6"}'::jsonb
        WHEN 'a0000000-0000-0000-0000-0000000001b3' THEN '{"locationId":"a0000000-0000-0000-0000-000000000001","cropCycleId":"a0000000-0000-0000-0000-000000000042","quantity":2.40,"unit":"tonnes","qualityGrade":"A","harvestDate":"2026-03-15"}'::jsonb
        ELSE claim_data
    END,
    chain = 'celo',
    status = 'published'
WHERE id IN (
    'a0000000-0000-0000-0000-0000000001b0',
    'a0000000-0000-0000-0000-0000000001b1',
    'a0000000-0000-0000-0000-0000000001b2',
    'a0000000-0000-0000-0000-0000000001b3'
);

UPDATE attestation_request
SET schema_id = 'a0000000-0000-0000-0000-0000000001e1',
    chain = 'celo',
    resolver_address = '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad',
    status = 'published',
    execution_status = 'confirmed',
    metadata = COALESCE(metadata, '{}'::jsonb) || '{"primary_chain":"celo","resolver":"0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad","private_evidence_policy":"store hashes and CIDs only"}'::jsonb,
    updated_at = NOW()
WHERE id = 'a0000000-0000-0000-0000-000000000550';

UPDATE mrv_event
SET attestation_record_id = 'a0000000-0000-0000-0000-0000000001b2',
    status = 'published',
    metadata = COALESCE(metadata, '{}'::jsonb) || '{"pipeline":"Farm activity -> structured payload -> IPFS record -> Farm Registry event -> EAS attestation -> public Data Hub -> annual impact report"}'::jsonb,
    updated_at = NOW()
WHERE id = 'a0000000-0000-0000-0000-000000000540';

UPDATE agent_task
SET inputs = inputs || '{"farm_id":"kokonut-adelphi"}'::jsonb,
    output = output || '{"registry_slug":"kokonut-adelphi"}'::jsonb
WHERE id = 'a0000000-0000-0000-0000-000000000562';

UPDATE farm_activity
SET description = replace(replace(replace(replace(replace(replace(description,
    'maize', 'lettuce'), 'Maize', 'Lettuce'),
    'cassava', 'passion fruit'), 'Cassava', 'Passion fruit'),
    'beans', 'eggs'), 'Beans', 'Eggs'),
    updated_at = NOW()
WHERE location_id = 'a0000000-0000-0000-0000-000000000001';

UPDATE field_note
SET content = replace(replace(replace(replace(replace(replace(content,
    'maize', 'lettuce'), 'Maize', 'Lettuce'),
    'cassava', 'passion fruit'), 'Cassava', 'Passion fruit'),
    'beans', 'eggs'), 'Beans', 'Eggs')
WHERE location_id = 'a0000000-0000-0000-0000-000000000001';

UPDATE expense_event
SET vendor = CASE vendor
        WHEN 'AgroSupplies Kenya' THEN 'Adelphi Bioinputs Network'
        WHEN 'Kisumu Water Co' THEN 'Adelphi Water Cooperative'
        WHEN 'Kisumu Agro Mechanics' THEN 'Adelphi Farm Services'
        WHEN 'Kisumu Transport Co' THEN 'Dominican Transport Cooperative'
        WHEN 'Kenya Power' THEN 'Local Utilities Cooperative'
        WHEN 'Kisumu County Land Board' THEN 'Adelphi Land Stewardship'
        WHEN 'Kisumu Agricultural Consultants' THEN 'Dominican Agronomy Advisors'
        ELSE vendor
    END,
    description = replace(replace(replace(replace(replace(replace(description,
        'maize', 'lettuce'), 'Maize', 'Lettuce'),
        'cassava', 'passion fruit'), 'Cassava', 'Passion fruit'),
        'beans', 'eggs'), 'Beans', 'Eggs')
WHERE location_id = 'a0000000-0000-0000-0000-000000000001';

UPDATE governance_event
SET wallet_id = 'a0000000-0000-0000-0000-000000000080',
    protocol_id = (SELECT id FROM protocol WHERE slug = 'kokonut-treasury'),
    chain = 'gnosis',
    proposal_title = CASE proposal_id
        WHEN 'P001' THEN 'Fund Adelphi syntropic bed buildout'
        WHEN 'P002' THEN 'Allocate funds for biofactory and nursery maintenance'
        WHEN 'P003' THEN 'Fund community field worker stipends'
        ELSE proposal_title
    END,
    token = CASE WHEN token = 'ETH' THEN 'vKKN' ELSE token END,
    metadata = COALESCE(metadata, '{}'::jsonb) || '{"governance_layer":"moloch_v2","alignment":"kokonut-adelphi"}'::jsonb
WHERE proposal_id IN ('P001', 'P002', 'P003')
  AND chain <> 'gnosis';

-- Adelphi framework mappings.
INSERT INTO farm_impact_mapping (location_id, framework_key, dimension_key, sdg_number, capital_key, pillar_key, claim, evidence_path, evidence_maturity, reporting_period, status, metadata) VALUES
('a0000000-0000-0000-0000-000000000001', 'sdg', NULL, 1, NULL, NULL, 'Adelphi supports income resilience through farm operations, local sales, and public goods allocation.', 'farm_registry_record.revenue_streams + value_flow_event', 'measured', '2025-2026', 'published', '{"tier":"primary"}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'sdg', NULL, 2, NULL, NULL, 'Adelphi produces diversified local food including lettuce, passion fruit, coconut, eggs, and Indian yam.', 'crop_cycle + harvest_event', 'measured', '2025-2026', 'published', '{"tier":"primary"}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'sdg', NULL, 5, NULL, NULL, 'Adelphi is modeled as a women-led and community-first farm operation.', 'farm_registry_record.source_raw', 'published', '2025-2026', 'published', '{"tier":"primary"}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'sdg', NULL, 8, NULL, NULL, 'Adelphi creates regenerative work pathways through field operations, MRV, nursery, and biofactory activities.', 'labor_event + guild_contribution', 'measured', '2025-2026', 'published', '{"tier":"primary"}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'sdg', NULL, 15, NULL, NULL, 'Syntropic and agroforestry establishment improves life-on-land outcomes through biodiversity, living cover, and soil regeneration.', 'farm_practice_event + environmental_baseline', 'measured', '2025-2026', 'published', '{"tier":"primary"}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'eight_forms_capital', NULL, NULL, 'natural', NULL, 'Natural capital is tracked through soil cover, biodiversity, water, and vegetation evidence.', 'farm_practice_event + environmental_baseline', 'measured', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'eight_forms_capital', NULL, NULL, 'financial', NULL, 'Financial capital is tracked through sales, expenses, treasury events, and public goods allocation.', 'sales_event + expense_event + treasury_event', 'measured', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'eight_forms_capital', NULL, NULL, 'social', NULL, 'Social capital is tracked through community-first operations, partner records, and Guild contribution history.', 'partner + guild_contribution', 'measured', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'eight_forms_capital', NULL, NULL, 'human', NULL, 'Human capital is tracked through farm roles, training, field work, and MRV coordination.', 'staff + labor_event', 'measured', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'eight_forms_capital', NULL, NULL, 'material', NULL, 'Material capital is tracked through the nursery, biofactory, poultry loop, and farm infrastructure.', 'infrastructure_asset + farm_zone', 'measured', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'ebf', 'ebf_environmental', NULL, NULL, NULL, 'Environmental benefits are represented by syntropic establishment and regeneration practice evidence.', 'farm_practice_event + attestation_record', 'verified', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'ebf', 'ebf_economic', NULL, NULL, NULL, 'Economic benefits are represented by verified revenue, costs, treasury events, and public goods allocation.', 'metric_value + value_flow_event', 'verified', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'crisp', 'crisp_evidence', NULL, NULL, NULL, 'Evidence quality risk is reduced by source lineage, payload hashes, CIDs, and Celo attestation metadata.', 'mrv_event + attestation_request', 'verified', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'pillars_value', NULL, NULL, NULL, 'public_goods', 'Adelphi includes a 10% public goods allocation in its common data schema record.', 'farm_registry_record.public_goods_allocation_pct', 'published', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'pillars_value', NULL, NULL, NULL, 'risk', 'Adelphi risk evidence is tracked through CRISP dimensions, MRV lineage, and governance records.', 'farm_impact_mapping + governance_event', 'measured', '2025-2026', 'published', '{}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO farm_zone (id, location_id, plot_id, zone_key, name, zone_type, area_m2, description, status, metadata) VALUES
('a0000000-0000-0000-0000-000000000700', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', 'adelphi-syntropic-beds', 'Syntropic Beds', 'syntropic_plot', 7838.0000, 'Primary syntropic crop beds for lettuce, Indian yam, and living cover.', 'active', '{"source":"kokonut knowledge base"}'::jsonb),
('a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'adelphi-agroforestry-corridor', 'Agroforestry Corridor', 'agroforestry', 4500.0000, 'Passion fruit, coconut, biodiversity, and multi-strata planting corridor.', 'active', '{"source":"kokonut knowledge base"}'::jsonb),
('a0000000-0000-0000-0000-000000000702', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000022', 'adelphi-nursery-biofactory', 'Nursery And Biofactory', 'biofactory', 1000.0000, 'Nursery, bioinput, compost tea, and biofertility production zone.', 'active', '{"source":"kokonut knowledge base"}'::jsonb),
('a0000000-0000-0000-0000-000000000703', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000022', 'adelphi-poultry-loop', 'Poultry Loop', 'poultry', 500.0000, 'Egg production and animal-integration fertility loop.', 'active', '{"product":"eggs"}'::jsonb)
ON CONFLICT (zone_key) DO UPDATE SET
    location_id = EXCLUDED.location_id,
    plot_id = EXCLUDED.plot_id,
    name = EXCLUDED.name,
    zone_type = EXCLUDED.zone_type,
    area_m2 = EXCLUDED.area_m2,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO farm_practice_event (id, location_id, zone_id, principle_key, practice_type, event_date, description, status, source_system, source_id, source_raw, metadata) VALUES
('a0000000-0000-0000-0000-000000000710', 'a0000000-0000-0000-0000-000000000001', (SELECT id FROM farm_zone WHERE zone_key = 'adelphi-syntropic-beds'), 'soil_protection', 'mulch_and_biochar', '2025-10-05', 'Applied mulch, compost, and biochar to protect soil and establish syntropic beds.', 'published', 'pilot_seed', 'adelphi-practice-soil-protection-2025-10', '{"evidence":"seeded practice evidence"}'::jsonb, '{}'::jsonb),
('a0000000-0000-0000-0000-000000000711', 'a0000000-0000-0000-0000-000000000001', (SELECT id FROM farm_zone WHERE zone_key = 'adelphi-syntropic-beds'), 'living_cover', 'living_cover_establishment', '2025-10-12', 'Established living cover and crop beds to reduce bare soil in active production areas.', 'published', 'pilot_seed', 'adelphi-practice-living-cover-2025-10', '{"evidence":"seeded practice evidence"}'::jsonb, '{}'::jsonb),
('a0000000-0000-0000-0000-000000000712', 'a0000000-0000-0000-0000-000000000001', (SELECT id FROM farm_zone WHERE zone_key = 'adelphi-agroforestry-corridor'), 'biodiversity', 'multi_strata_planting', '2025-11-01', 'Planted passion fruit, coconut, and support species for multi-strata biodiversity.', 'published', 'pilot_seed', 'adelphi-practice-biodiversity-2025-11', '{"evidence":"seeded practice evidence"}'::jsonb, '{}'::jsonb),
('a0000000-0000-0000-0000-000000000713', 'a0000000-0000-0000-0000-000000000001', (SELECT id FROM farm_zone WHERE zone_key = 'adelphi-poultry-loop'), 'animal_integration', 'poultry_fertility_loop', '2026-01-10', 'Integrated poultry and egg production into the farm nutrient and food production loop.', 'published', 'pilot_seed', 'adelphi-practice-poultry-2026-01', '{"evidence":"seeded practice evidence"}'::jsonb, '{}'::jsonb),
('a0000000-0000-0000-0000-000000000714', 'a0000000-0000-0000-0000-000000000001', (SELECT id FROM farm_zone WHERE zone_key = 'adelphi-nursery-biofactory'), 'organic_inputs', 'bioinput_production', '2025-10-10', 'Produced compost tea and biofertilizer in the Adelphi biofactory for bed establishment.', 'published', 'pilot_seed', 'adelphi-practice-bioinputs-2025-10', '{"evidence":"seeded practice evidence"}'::jsonb, '{}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    zone_id = EXCLUDED.zone_id,
    principle_key = EXCLUDED.principle_key,
    practice_type = EXCLUDED.practice_type,
    event_date = EXCLUDED.event_date,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    source_system = EXCLUDED.source_system,
    source_id = EXCLUDED.source_id,
    source_raw = EXCLUDED.source_raw,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Colony-backed Guild seed records. Colony is the execution/reputation layer;
-- Moloch/Gnosis remains treasury governance.
UPDATE colony_instance
SET status = 'planned',
    metadata = COALESCE(metadata, '{}'::jsonb) || '{"execution_layer":"Colony","treasury_governance":"Moloch v2 on Gnosis","source_repos":["JoinColony/colonyNetwork","JoinColony/colonyJS","JoinColony/Colony-Whitepaper"]}'::jsonb,
    updated_at = NOW()
WHERE colony_key = 'kokonut-guilds';

INSERT INTO guild_contributor (id, wallet_address, display_name, contributor_type, status, metadata) VALUES
('a0000000-0000-0000-0000-000000000800', '0x0000000000000000000000000000000000000001', 'Kokonut Tech Steward', 'builder', 'active', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000801', '0x0000000000000000000000000000000000000002', 'Impact Methodology Steward', 'researcher', 'active', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000802', '0x0000000000000000000000000000000000000003', 'Adelphi Field Steward', 'operator', 'active', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000803', '0x0000000000000000000000000000000000000004', 'Governance Steward', 'steward', 'active', '{}'::jsonb)
ON CONFLICT (wallet_address) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    contributor_type = EXCLUDED.contributor_type,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO guild_contribution (id, guild_id, contributor_id, contribution_type, title, description, contribution_date, evidence_url, points_awarded, review_status, metadata) VALUES
('a0000000-0000-0000-0000-000000000810', (SELECT id FROM kokonut_guild WHERE guild_key = 'technology'), (SELECT id FROM guild_contributor WHERE wallet_address = '0x0000000000000000000000000000000000000001'), 'data_pipeline', 'Adelphi MRV metadata alignment', 'Linked Adelphi registry, Celo EAS metadata, and public Data Hub lineage.', '2026-03-20', 'https://hub.kokonut.network/projects/41', 25.000000, 'published', '{"colony_layer":"planned"}'::jsonb),
('a0000000-0000-0000-0000-000000000811', (SELECT id FROM kokonut_guild WHERE guild_key = 'impact'), (SELECT id FROM guild_contributor WHERE wallet_address = '0x0000000000000000000000000000000000000002'), 'methodology', 'Adelphi impact framework mapping', 'Mapped Adelphi to SDGs, 8 Forms of Capital, EBF, CRISP, Pillars, and regeneration principles.', '2026-03-20', 'https://kokonut.network/kokonut-framework/Introduction', 30.000000, 'published', '{"colony_layer":"planned"}'::jsonb),
('a0000000-0000-0000-0000-000000000812', (SELECT id FROM kokonut_guild WHERE guild_key = 'community_partnerships'), (SELECT id FROM guild_contributor WHERE wallet_address = '0x0000000000000000000000000000000000000003'), 'field_operations', 'Adelphi field evidence coordination', 'Coordinated syntropic bed, nursery, biofactory, and poultry practice records.', '2026-03-20', 'https://hub.kokonut.network/projects/41', 20.000000, 'published', '{"colony_layer":"planned"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    guild_id = EXCLUDED.guild_id,
    contributor_id = EXCLUDED.contributor_id,
    contribution_type = EXCLUDED.contribution_type,
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    contribution_date = EXCLUDED.contribution_date,
    evidence_url = EXCLUDED.evidence_url,
    points_awarded = EXCLUDED.points_awarded,
    review_status = EXCLUDED.review_status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO guild_reputation_snapshot (guild_id, contributor_id, snapshot_date, reputation_amount, reputation_pct, source_system, source_id, metadata) VALUES
((SELECT id FROM kokonut_guild WHERE guild_key = 'technology'), (SELECT id FROM guild_contributor WHERE wallet_address = '0x0000000000000000000000000000000000000001'), '2026-03-31', 25.000000, 25.0000, 'colony', 'planned-technology-2026-03', '{}'::jsonb),
((SELECT id FROM kokonut_guild WHERE guild_key = 'impact'), (SELECT id FROM guild_contributor WHERE wallet_address = '0x0000000000000000000000000000000000000002'), '2026-03-31', 30.000000, 30.0000, 'colony', 'planned-impact-2026-03', '{}'::jsonb),
((SELECT id FROM kokonut_guild WHERE guild_key = 'community_partnerships'), (SELECT id FROM guild_contributor WHERE wallet_address = '0x0000000000000000000000000000000000000003'), '2026-03-31', 20.000000, 20.0000, 'colony', 'planned-community-2026-03', '{}'::jsonb)
ON CONFLICT (guild_id, contributor_id, snapshot_date) DO UPDATE SET
    reputation_amount = EXCLUDED.reputation_amount,
    reputation_pct = EXCLUDED.reputation_pct,
    source_system = EXCLUDED.source_system,
    source_id = EXCLUDED.source_id,
    metadata = EXCLUDED.metadata;

INSERT INTO dao_proposal (proposal_code, title, proposal_type, lifecycle_stage, venue, location_id, guild_id, moloch_proposal_id, colony_motion_id, requested_amount, requested_token, public_goods_allocation_pct, success_metrics, status, metadata) VALUES
('KOK-AD-001', 'Fund Adelphi syntropic bed buildout', 'farm_funding', 'executed', 'daohaus', 'a0000000-0000-0000-0000-000000000001', (SELECT id FROM kokonut_guild WHERE guild_key = 'impact'), 'P001', NULL, 500.000000, 'USDC', 10.000, 'Syntropic beds established and MRV payload published.', 'published', '{"treasury_chain":"gnosis","execution_layer":"moloch_v2"}'::jsonb),
('KOK-AD-002', 'Create Adelphi impact and MRV Guild bounty', 'guild_bounty', 'active', 'colony', 'a0000000-0000-0000-0000-000000000001', (SELECT id FROM kokonut_guild WHERE guild_key = 'impact'), NULL, 'planned-impact-motion-001', 30.000000, 'points', 0.000, 'Framework mapping and public attestation metadata completed.', 'published', '{"guild_execution":"colony","treasury_chain":"gnosis"}'::jsonb),
('KOK-AD-003', 'Publish Adelphi annual impact report pipeline', 'framework_upgrade', 'draft', 'forum', 'a0000000-0000-0000-0000-000000000001', (SELECT id FROM kokonut_guild WHERE guild_key = 'communications'), NULL, NULL, 0.000000, 'USDC', 10.000, 'Annual impact report generated from governed data and Celo attestation summaries.', 'draft', '{"pipeline":"Farm activity -> structured payload -> IPFS record -> Farm Registry event -> EAS attestation -> public Data Hub -> annual impact report"}'::jsonb)
ON CONFLICT (proposal_code) DO UPDATE SET
    title = EXCLUDED.title,
    proposal_type = EXCLUDED.proposal_type,
    lifecycle_stage = EXCLUDED.lifecycle_stage,
    venue = EXCLUDED.venue,
    location_id = EXCLUDED.location_id,
    guild_id = EXCLUDED.guild_id,
    moloch_proposal_id = EXCLUDED.moloch_proposal_id,
    colony_motion_id = EXCLUDED.colony_motion_id,
    requested_amount = EXCLUDED.requested_amount,
    requested_token = EXCLUDED.requested_token,
    public_goods_allocation_pct = EXCLUDED.public_goods_allocation_pct,
    success_metrics = EXCLUDED.success_metrics,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
