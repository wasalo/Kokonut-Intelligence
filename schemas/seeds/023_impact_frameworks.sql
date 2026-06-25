-- ============================================================
-- Seed: Kokonut Framework reference data
-- ============================================================

-- Remove incomplete rows from older Baserow migration runs.
DELETE FROM sdg WHERE COALESCE(TRIM(name), '') = '';
DELETE FROM form_of_capital WHERE COALESCE(TRIM(name), '') = '';
DELETE FROM impact_dimension WHERE COALESCE(TRIM(name), '') = '';
DELETE FROM impact_framework WHERE COALESCE(TRIM(name), '') = '';

INSERT INTO impact_framework (framework_key, name, description, url, framework_type, status, metadata) VALUES
('kokonut_framework', 'Kokonut Framework', 'Farm operating system for comparable, fundable, governable, and verifiable regenerative farms.', 'https://kokonut.network/kokonut-framework/Introduction', 'operating_framework', 'active', '{"source":"kokonut knowledge base"}'::jsonb),
('sdg', 'Sustainable Development Goals', 'UN SDG evidence map for regenerative farm activity and annual reporting.', 'https://sdgs.un.org/goals', 'impact_framework', 'active', '{"primary_sdgs":[1,2,5,8,15]}'::jsonb),
('ebf', 'Ecological Benefits Framework', 'Framework for interpreting ecological and community benefits from verified farm data.', 'https://ebfcommons.org', 'impact_framework', 'active', '{"role":"annual reporting"}'::jsonb),
('crisp', 'Carbon Risk Scoring', 'Risk interpretation layer for carbon and ecological outcome credibility.', NULL, 'risk_framework', 'active', '{"role":"risk review"}'::jsonb),
('eight_forms_capital', '8 Forms of Capital', 'Value-accounting lens across natural, financial, social, human, material, intellectual, cultural, and health capital.', 'https://kokonut.network/kokonut-framework/framework-components/framework-features/8-forms-of-capital', 'value_framework', 'active', '{}'::jsonb),
('pillars_value', 'Pillars of Value', 'Six proposal and reporting questions: what, who, how much, contribution, risk, and public goods.', 'https://kokonut.network/kokonut-framework/framework-components/pillars-of-value', 'evaluation_framework', 'active', '{}'::jsonb),
('regeneration_principles', '5 Principles of Regeneration', 'Operating standard for soil protection, biodiversity, animal integration, living roots/perennials, and organic inputs.', 'https://kokonut.network/kokonut-framework/framework-components/framework-features/5-principles-of-regeneration', 'practice_framework', 'active', '{}'::jsonb)
ON CONFLICT (framework_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    url = EXCLUDED.url,
    framework_type = EXCLUDED.framework_type,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO impact_dimension (dimension_key, framework_id, name, description, dimension_type, sort_order, is_active, metadata) VALUES
('ebf_environmental', (SELECT id FROM impact_framework WHERE framework_key = 'ebf'), 'Environmental', 'Ecological health, biodiversity, vegetation, soil, water, and carbon evidence.', 'ebf_dimension', 1, TRUE, '{}'::jsonb),
('ebf_economic', (SELECT id FROM impact_framework WHERE framework_key = 'ebf'), 'Economic', 'Farm revenue, public goods allocation, jobs, and local economic circulation.', 'ebf_dimension', 2, TRUE, '{}'::jsonb),
('ebf_social', (SELECT id FROM impact_framework WHERE framework_key = 'ebf'), 'Social', 'Community wellbeing, training, participation, and local capacity.', 'ebf_dimension', 3, TRUE, '{}'::jsonb),
('ebf_sustainability', (SELECT id FROM impact_framework WHERE framework_key = 'ebf'), 'Sustainability', 'Long-term resilience across the 8 Forms of Capital and governance evidence.', 'ebf_dimension', 4, TRUE, '{}'::jsonb),
('crisp_operational', (SELECT id FROM impact_framework WHERE framework_key = 'crisp'), 'Operational Risk', 'Execution, labor, data quality, and farm management risk.', 'crisp_risk', 1, TRUE, '{}'::jsonb),
('crisp_climate', (SELECT id FROM impact_framework WHERE framework_key = 'crisp'), 'Climate Risk', 'Weather, drought, flood, heat, storm, and seasonal variability risk.', 'crisp_risk', 2, TRUE, '{}'::jsonb),
('crisp_market', (SELECT id FROM impact_framework WHERE framework_key = 'crisp'), 'Market Risk', 'Buyer access, price volatility, certification, and revenue timing risk.', 'crisp_risk', 3, TRUE, '{}'::jsonb),
('crisp_policy', (SELECT id FROM impact_framework WHERE framework_key = 'crisp'), 'Policy And Methodology Risk', 'Certification, carbon methodology, governance, and external review risk.', 'crisp_risk', 4, TRUE, '{}'::jsonb),
('crisp_evidence', (SELECT id FROM impact_framework WHERE framework_key = 'crisp'), 'Evidence Quality Risk', 'Completeness, provenance, CIDs, attestations, and review-quality risk.', 'crisp_risk', 5, TRUE, '{}'::jsonb)
ON CONFLICT (dimension_key) DO UPDATE SET
    framework_id = EXCLUDED.framework_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dimension_type = EXCLUDED.dimension_type,
    sort_order = EXCLUDED.sort_order,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO sdg (sdg_number, name, short_name, description, evidence_maturity, tier, is_active, metadata) VALUES
(1, 'SDG 1 — No Poverty', 'No Poverty', 'Jobs, income resilience, public goods allocation, and farm revenue circulation.', 'primary', 'primary', TRUE, '{"kokonut_relationship":"jobs_income_public_goods"}'::jsonb),
(2, 'SDG 2 — Zero Hunger', 'Zero Hunger', 'Diversified local food production, harvests, eggs, and resilient crop cycles.', 'primary', 'primary', TRUE, '{"kokonut_relationship":"food_production"}'::jsonb),
(3, 'SDG 3 — Good Health and Well-being', 'Good Health and Well-being', 'Fresh food access, nature, community programming, and reduced synthetic-input exposure.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(4, 'SDG 4 — Quality Education', 'Quality Education', 'Farm workshops, open documentation, and regenerative agriculture training.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(5, 'SDG 5 — Gender Equality', 'Gender Equality', 'Women-led ownership and governance participation where implemented.', 'primary', 'primary', TRUE, '{"kokonut_relationship":"women_led_operations"}'::jsonb),
(6, 'SDG 6 — Clean Water and Sanitation', 'Clean Water and Sanitation', 'Soil cover, erosion control, runoff reduction, and watershed health.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(7, 'SDG 7 — Affordable and Clean Energy', 'Affordable and Clean Energy', 'Reduced synthetic-input dependence and possible renewable systems.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(8, 'SDG 8 — Decent Work and Economic Growth', 'Decent Work and Economic Growth', 'Farm jobs, skills, local enterprise, and regenerative work pathways.', 'primary', 'primary', TRUE, '{"kokonut_relationship":"jobs_skills_local_enterprise"}'::jsonb),
(9, 'SDG 9 — Industry, Innovation and Infrastructure', 'Industry, Innovation and Infrastructure', 'Farm Registry, Data Hub, AI agents, and open MRV infrastructure.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(10, 'SDG 10 — Reduced Inequalities', 'Reduced Inequalities', 'Contribution paths, Guilds, local participation, and public goods allocation.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(11, 'SDG 11 — Sustainable Cities and Communities', 'Sustainable Cities and Communities', 'Community hubs, food access, educational spaces, and resilient local systems.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(12, 'SDG 12 — Responsible Consumption and Production', 'Responsible Consumption and Production', 'Organic inputs, closed-loop fertility, local markets, and waste reduction.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(13, 'SDG 13 — Climate Action', 'Climate Action', 'Biochar, agroforestry, vegetation health, soil regeneration, and resilience.', 'co_benefit', 'secondary', TRUE, '{"claim_safety":"climate co-benefit until methodology verified"}'::jsonb),
(14, 'SDG 14 — Life Below Water', 'Life Below Water', 'Reduced runoff and watershed-to-coast co-benefits where relevant.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(15, 'SDG 15 — Life on Land', 'Life on Land', 'Biodiversity, agroforestry, living roots, erosion control, and nursery propagation.', 'primary', 'primary', TRUE, '{"kokonut_relationship":"biodiversity_soil_living_roots"}'::jsonb),
(16, 'SDG 16 — Peace, Justice and Strong Institutions', 'Peace, Justice and Strong Institutions', 'Transparent DAO governance, proposal processes, and public records.', 'secondary', 'secondary', TRUE, '{}'::jsonb),
(17, 'SDG 17 — Partnerships for the Goals', 'Partnerships for the Goals', 'Public goods funders, MRV partners, open-source collaborators, and local partnerships.', 'secondary', 'secondary', TRUE, '{}'::jsonb)
ON CONFLICT (sdg_number) DO UPDATE SET
    name = EXCLUDED.name,
    short_name = EXCLUDED.short_name,
    description = EXCLUDED.description,
    evidence_maturity = EXCLUDED.evidence_maturity,
    tier = EXCLUDED.tier,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO form_of_capital (capital_key, name, description, kokonut_question, evidence_examples, sort_order, is_active, metadata) VALUES
('natural', 'Natural Capital', 'Soil, water, biodiversity, vegetation, carbon, and ecosystem health.', 'Is the land becoming healthier over time?', ARRAY['soil moisture', 'NDVI', 'species records', 'biochar logs'], 1, TRUE, '{}'::jsonb),
('financial', 'Financial Capital', 'Revenue, treasury, funding, costs, and public goods allocation.', 'Can the farm sustain operations and distribute value responsibly?', ARRAY['sales records', 'treasury events', 'public goods allocation'], 2, TRUE, '{}'::jsonb),
('social', 'Social Capital', 'Trust, relationships, coordination, participation, and community networks.', 'Is the farm strengthening local and network relationships?', ARRAY['events', 'attendance', 'Guild contribution records'], 3, TRUE, '{}'::jsonb),
('human', 'Human Capital', 'Skills, knowledge, safety, training, and leadership capacity.', 'Are people gaining the capability to operate and replicate regeneration?', ARRAY['training logs', 'skills assessments', 'role records'], 4, TRUE, '{}'::jsonb),
('material', 'Material Capital', 'Infrastructure, tools, equipment, built assets, and physical systems.', 'Does the farm have the physical base to keep working?', ARRAY['infrastructure assets', 'maintenance events', 'equipment status'], 5, TRUE, '{}'::jsonb),
('intellectual', 'Intellectual Capital', 'Data, documentation, methods, open-source tools, and research.', 'Is the network learning in a way others can reuse?', ARRAY['documentation', 'MRV payloads', 'open-source commits'], 6, TRUE, '{}'::jsonb),
('cultural', 'Cultural Capital', 'Stories, traditions, local identity, land memory, and heritage species.', 'Is the farm preserving and renewing cultural connection to land?', ARRAY['founder stories', 'heritage species', 'community programs'], 7, TRUE, '{}'::jsonb),
('health', 'Health Capital', 'Food quality, worker wellbeing, community nutrition, and safe conditions.', 'Is the farm supporting healthier people and safer work?', ARRAY['harvest records', 'food distribution', 'safety logs'], 8, TRUE, '{}'::jsonb)
ON CONFLICT (capital_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    kokonut_question = EXCLUDED.kokonut_question,
    evidence_examples = EXCLUDED.evidence_examples,
    sort_order = EXCLUDED.sort_order,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO pillar_of_value (pillar_key, name, core_question, schema_connections, sort_order, status, metadata) VALUES
('what', 'WHAT', 'What value is the farm designed to create?', ARRAY['project_summary', 'revenue_streams'], 1, 'active', '{}'::jsonb),
('who', 'WHO', 'Who benefits directly and indirectly?', ARRAY['target_market', 'local_problem'], 2, 'active', '{}'::jsonb),
('how_much', 'HOW MUCH', 'At what scale will value be created?', ARRAY['land_size', 'forecasted_budget', 'public_goods_allocation'], 3, 'active', '{}'::jsonb),
('contribution', 'CONTRIBUTION', 'What tangible contributions does the farm add?', ARRAY['proposed_solution'], 4, 'active', '{}'::jsonb),
('risk', 'RISK', 'What could fail, and how will it be mitigated?', ARRAY['risk assessment', 'CRISP', 'milestones'], 5, 'active', '{}'::jsonb),
('public_goods', 'PUBLIC GOODS', 'What community benefit is built into the model?', ARRAY['public_goods_allocation'], 6, 'active', '{}'::jsonb)
ON CONFLICT (pillar_key) DO UPDATE SET
    name = EXCLUDED.name,
    core_question = EXCLUDED.core_question,
    schema_connections = EXCLUDED.schema_connections,
    sort_order = EXCLUDED.sort_order,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO regeneration_principle (principle_key, name, description, evidence_examples, sort_order, status, metadata) VALUES
('soil_protection', 'Protect and regenerate soil', 'Minimize disturbance, build organic matter, use mulch, biochar, compost, and soil observations.', ARRAY['soil samples', 'biochar logs', 'mulch or compost records'], 1, 'active', '{}'::jsonb),
('living_cover', 'Maintain living roots and soil cover', 'Use cover crops, ground cover, perennial roots, and erosion-control plants to avoid bare soil.', ARRAY['field observations', 'cover crop records', 'remote sensing'], 2, 'active', '{}'::jsonb),
('biodiversity', 'Increase biodiversity', 'Use diverse crops, agroforestry, native species propagation, habitat corridors, and multi-strata planting.', ARRAY['species observation', 'nursery inventory', 'GPS plant records'], 3, 'active', '{}'::jsonb),
('animal_integration', 'Integrate animals responsibly', 'Use livestock or poultry loops where animals support fertility, pest balance, and food production.', ARRAY['poultry records', 'manure processing logs', 'egg records'], 4, 'active', '{}'::jsonb),
('organic_inputs', 'Cycle organic inputs', 'Use compost, biofertilizers, humic acids, organic urea, biochar, and farm residues to reduce synthetic dependency.', ARRAY['inventory events', 'biofactory logs', 'input application records'], 5, 'active', '{}'::jsonb)
ON CONFLICT (principle_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    evidence_examples = EXCLUDED.evidence_examples,
    sort_order = EXCLUDED.sort_order,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO colony_instance (colony_key, name, chain, chain_id, colony_address, native_token_address, network_address, status, metadata) VALUES
('kokonut-guilds', 'Kokonut Guilds Colony', 'gnosis', 100, NULL, NULL, NULL, 'planned', '{"framework":"Colony","source":"JoinColony/colonyNetwork","sdk":"JoinColony/colonyJS","role":"Guild contribution and reputation layer"}'::jsonb)
ON CONFLICT (colony_key) DO UPDATE SET
    name = EXCLUDED.name,
    chain = EXCLUDED.chain,
    chain_id = EXCLUDED.chain_id,
    colony_address = EXCLUDED.colony_address,
    native_token_address = EXCLUDED.native_token_address,
    network_address = EXCLUDED.network_address,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO kokonut_guild (guild_key, colony_instance_id, name, purpose, colony_domain_id, colony_skill_id, status, metadata) VALUES
('technology', (SELECT id FROM colony_instance WHERE colony_key = 'kokonut-guilds'), 'Technology Guild', 'Smart contracts, MRV data pipelines, APIs, dashboards, frontend, open-source tooling, and AI integrations.', 1, NULL, 'active', '{}'::jsonb),
('impact', (SELECT id FROM colony_instance WHERE colony_key = 'kokonut-guilds'), 'Impact Guild', 'MRV methodology, EBF reporting, CRISP risk scoring, SDG alignment, field validation, biodiversity, and impact attestations.', 2, NULL, 'active', '{}'::jsonb),
('communications', (SELECT id FROM colony_instance WHERE colony_key = 'kokonut-guilds'), 'Communications Guild', 'Documentation, content strategy, onboarding, grant storytelling, social updates, and educational material.', 3, NULL, 'active', '{}'::jsonb),
('governance', (SELECT id FROM colony_instance WHERE colony_key = 'kokonut-guilds'), 'Governance Guild', 'Proposal review, governance amendments, member onboarding, dispute resolution, and cross-Guild coordination.', 4, NULL, 'active', '{}'::jsonb),
('finance', (SELECT id FROM colony_instance WHERE colony_key = 'kokonut-guilds'), 'Finance Guild', 'Treasury reporting, farm financial modeling, budgets, grant finance, stablecoin strategy, and public goods allocation.', 5, NULL, 'active', '{}'::jsonb),
('community_partnerships', (SELECT id FROM colony_instance WHERE colony_key = 'kokonut-guilds'), 'Community & Partnerships Guild', 'Farmer onboarding, institutional partnerships, local events, ReFi relationships, and cooperative growth.', 6, NULL, 'active', '{}'::jsonb)
ON CONFLICT (guild_key) DO UPDATE SET
    colony_instance_id = EXCLUDED.colony_instance_id,
    name = EXCLUDED.name,
    purpose = EXCLUDED.purpose,
    colony_domain_id = EXCLUDED.colony_domain_id,
    colony_skill_id = EXCLUDED.colony_skill_id,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
