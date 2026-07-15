-- ============================================================
-- Seed: Business Architecture Capability Map
-- ============================================================
-- Hybrid taxonomy: Guilds (strategic) → Capabilities (core) → Processes → Services

INSERT INTO service_registry (name, version, category, description, status) VALUES
('capability_map', '1.0.0', 'analytics', 'Business capability hierarchy, maturity, process mapping, and service coverage', 'active'),
('strategy_map', '1.0.0', 'analytics', 'Balanced Scorecard strategy mapping and initiative execution tracking', 'active'),
('vision_mission', '1.0.0', 'analytics', 'Governed vision, mission, and values statement management', 'active'),
('value_stream_defs', '1.0.0', 'analytics', 'Formal value stream definitions, stages, observations, and performance', 'active')
ON CONFLICT (name) DO UPDATE SET
    version = EXCLUDED.version,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- ============================================================
-- Guild-level capabilities (strategic tier)
-- ============================================================
INSERT INTO business_capability (name, description, capability_type, parent_id, guild_key, maturity_level, owner_role, status) VALUES
('Technology Platform', 'Smart contracts, MRV data pipelines, APIs, dashboards, and AI integrations', 'strategic', NULL, 'technology', 4, 'Technology Guild', 'active'),
('Impact Intelligence', 'MRV methodology, EBF reporting, CRISP risk scoring, SDG alignment, and impact attestations', 'strategic', NULL, 'impact', 4, 'Impact Guild', 'active'),
('Communications & Content', 'Documentation, content strategy, onboarding, grant storytelling, and educational material', 'strategic', NULL, 'communications', 3, 'Communications Guild', 'active'),
('Platform Governance', 'Proposal review, governance amendments, member onboarding, dispute resolution, and cross-Guild coordination', 'strategic', NULL, 'governance', 4, 'Governance Guild', 'active'),
('Financial Operations', 'Treasury reporting, farm financial modeling, budgets, grant finance, stablecoin strategy, and public goods allocation', 'strategic', NULL, 'finance', 3, 'Finance Guild', 'active'),
('Community & Partnerships', 'Farmer onboarding, institutional partnerships, local events, ReFi relationships, and cooperative growth', 'strategic', NULL, 'community_partnerships', 3, 'Community & Partnerships Guild', 'active')
ON CONFLICT (name, guild_key) DO UPDATE SET
    description = EXCLUDED.description,
    capability_type = EXCLUDED.capability_type,
    guild_key = EXCLUDED.guild_key,
    maturity_level = EXCLUDED.maturity_level,
    owner_role = EXCLUDED.owner_role,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================
-- Core capabilities (operational tier) — Technology Guild
-- ============================================================
INSERT INTO business_capability (name, description, capability_type, parent_id, guild_key, maturity_level, owner_role, status) VALUES
('Event Delivery', 'Durable event bus delivery, retry, and dead-letter management', 'core',
    (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'),
    'technology', 4, 'Technology Guild', 'active'),
('Process Analytics', 'Process mining, predictive BPM, SPC control charts, and health dashboards', 'core',
    (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'),
    'technology', 4, 'Technology Guild', 'active'),
('Agent Execution', 'AI agent task lifecycle, review, and safety enforcement', 'core',
    (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'),
    'technology', 4, 'Technology Guild', 'active'),
('Data Publication', 'Governed data stream posts, content-hash storage, IRI resolution, and RDF triples', 'core',
    (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'),
    'technology', 4, 'Technology Guild', 'active'),
('Metric Governance', 'Metric computation, verification, governed storage, and BRM performance reference model', 'core',
    (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'),
    'technology', 4, 'Technology Guild', 'active'),
('Systems Thinking', 'Causal loops, leverage points, archetypes, double-loop learning, and stock-flow simulation', 'core',
    (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'),
    'technology', 3, 'Technology Guild', 'active')
ON CONFLICT (name, guild_key) DO UPDATE SET
    description = EXCLUDED.description,
    capability_type = EXCLUDED.capability_type,
    parent_id = EXCLUDED.parent_id,
    maturity_level = EXCLUDED.maturity_level,
    owner_role = EXCLUDED.owner_role,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================
-- Core capabilities — Impact Guild
-- ============================================================
INSERT INTO business_capability (name, description, capability_type, parent_id, guild_key, maturity_level, owner_role, status) VALUES
('Impact Verification', 'Impact claim creation, evidence review, and EBF/CRISP alignment', 'core',
    (SELECT id FROM business_capability WHERE name = 'Impact Intelligence' AND guild_key = 'impact'),
    'impact', 4, 'Impact Guild', 'active'),
('Pest & Disease Management', 'IPM scouting, thresholds, interventions, pesticide tracking, and compliance', 'core',
    (SELECT id FROM business_capability WHERE name = 'Impact Intelligence' AND guild_key = 'impact'),
    'impact', 3, 'Impact Guild', 'active'),
('Landscape & Biodiversity', 'Habitat, corridor, hedgerow, buffer, and pollinator tracking', 'core',
    (SELECT id FROM business_capability WHERE name = 'Impact Intelligence' AND guild_key = 'impact'),
    'impact', 3, 'Impact Guild', 'active'),
('Soil & Nutrient Management', 'Nutrient balance budgeting, soil testing, crop rotation, and recommendation engine', 'core',
    (SELECT id FROM business_capability WHERE name = 'Impact Intelligence' AND guild_key = 'impact'),
    'impact', 3, 'Impact Guild', 'active'),
('Digital Twin Simulation', 'Crop-growth simulation, what-if scenarios, and trajectory forecasting', 'core',
    (SELECT id FROM business_capability WHERE name = 'Impact Intelligence' AND guild_key = 'impact'),
    'impact', 3, 'Impact Guild', 'active')
ON CONFLICT (name, guild_key) DO UPDATE SET
    description = EXCLUDED.description,
    capability_type = EXCLUDED.capability_type,
    parent_id = EXCLUDED.parent_id,
    maturity_level = EXCLUDED.maturity_level,
    owner_role = EXCLUDED.owner_role,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================
-- Core capabilities — Communications Guild
-- ============================================================
INSERT INTO business_capability (name, description, capability_type, parent_id, guild_key, maturity_level, owner_role, status) VALUES
('Reporting & Analytics', 'Multi-type report generation, dashboard refresh, and dataset management', 'core',
    (SELECT id FROM business_capability WHERE name = 'Communications & Content' AND guild_key = 'communications'),
    'communications', 4, 'Communications Guild', 'active'),
('Extension & Training', 'Learning modules, peer groups, delivery channels, and effectiveness tracking', 'core',
    (SELECT id FROM business_capability WHERE name = 'Communications & Content' AND guild_key = 'communications'),
    'communications', 3, 'Communications Guild', 'active'),
('Stakeholder Feedback', 'Feedback collection, consent management, publication, and synthesis', 'core',
    (SELECT id FROM business_capability WHERE name = 'Communications & Content' AND guild_key = 'communications'),
    'communications', 3, 'Communications Guild', 'active')
ON CONFLICT (name, guild_key) DO UPDATE SET
    description = EXCLUDED.description,
    capability_type = EXCLUDED.capability_type,
    parent_id = EXCLUDED.parent_id,
    maturity_level = EXCLUDED.maturity_level,
    owner_role = EXCLUDED.owner_role,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================
-- Core capabilities — Governance Guild
-- ============================================================
INSERT INTO business_capability (name, description, capability_type, parent_id, guild_key, maturity_level, owner_role, status) VALUES
('Decision Management', 'Policy-driven decisions with human approval gates and escalation', 'core',
    (SELECT id FROM business_capability WHERE name = 'Platform Governance' AND guild_key = 'governance'),
    'governance', 4, 'Governance Guild', 'active'),
('Work Management', 'Task assignment, tracking, SLA enforcement, and completion', 'core',
    (SELECT id FROM business_capability WHERE name = 'Platform Governance' AND guild_key = 'governance'),
    'governance', 4, 'Governance Guild', 'active'),
('Process Governance', 'Process architecture, maturity assessment, gap analysis, and improvement', 'core',
    (SELECT id FROM business_capability WHERE name = 'Platform Governance' AND guild_key = 'governance'),
    'governance', 4, 'Governance Guild', 'active'),
('Emergency Response', 'Incident reporting, response coordination, and resolution tracking', 'core',
    (SELECT id FROM business_capability WHERE name = 'Platform Governance' AND guild_key = 'governance'),
    'governance', 3, 'Governance Guild', 'active')
ON CONFLICT (name, guild_key) DO UPDATE SET
    description = EXCLUDED.description,
    capability_type = EXCLUDED.capability_type,
    parent_id = EXCLUDED.parent_id,
    maturity_level = EXCLUDED.maturity_level,
    owner_role = EXCLUDED.owner_role,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================
-- Core capabilities — Finance Guild
-- ============================================================
INSERT INTO business_capability (name, description, capability_type, parent_id, guild_key, maturity_level, owner_role, status) VALUES
('Financial Planning', 'Budget creation, approval, variance analysis, and break-even modeling', 'core',
    (SELECT id FROM business_capability WHERE name = 'Financial Operations' AND guild_key = 'finance'),
    'finance', 3, 'Finance Guild', 'active'),
('Carbon Lifecycle', 'Carbon credit issuance, trading, retirement, and certificate generation', 'core',
    (SELECT id FROM business_capability WHERE name = 'Financial Operations' AND guild_key = 'finance'),
    'finance', 4, 'Finance Guild', 'active'),
('Digital Finance', 'Accounts, transactions, insurance, loans, and portfolio analysis', 'core',
    (SELECT id FROM business_capability WHERE name = 'Financial Operations' AND guild_key = 'finance'),
    'finance', 3, 'Finance Guild', 'active'),
('Marketplace Operations', 'Marketplace listings, price recording, orders, and evaluation', 'core',
    (SELECT id FROM business_capability WHERE name = 'Financial Operations' AND guild_key = 'finance'),
    'finance', 3, 'Finance Guild', 'active')
ON CONFLICT (name, guild_key) DO UPDATE SET
    description = EXCLUDED.description,
    capability_type = EXCLUDED.capability_type,
    parent_id = EXCLUDED.parent_id,
    maturity_level = EXCLUDED.maturity_level,
    owner_role = EXCLUDED.owner_role,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================
-- Core capabilities — Community & Partnerships Guild
-- ============================================================
INSERT INTO business_capability (name, description, capability_type, parent_id, guild_key, maturity_level, owner_role, status) VALUES
('Farm Operations', 'Farm activity recording, sensor ingestion, anomaly detection, and weather forecasting', 'core',
    (SELECT id FROM business_capability WHERE name = 'Community & Partnerships' AND guild_key = 'community_partnerships'),
    'community_partnerships', 4, 'Community & Partnerships Guild', 'active'),
('Harvest & Yield Management', 'Harvest event recording, yield monitoring, trend analysis, and benchmarking', 'core',
    (SELECT id FROM business_capability WHERE name = 'Community & Partnerships' AND guild_key = 'community_partnerships'),
    'community_partnerships', 4, 'Community & Partnerships Guild', 'active'),
('Cooperative Management', 'Cooperative creation, membership, assets, collective purchasing, and market orders', 'core',
    (SELECT id FROM business_capability WHERE name = 'Community & Partnerships' AND guild_key = 'community_partnerships'),
    'community_partnerships', 3, 'Community & Partnerships Guild', 'active'),
('Traceability', 'Batch tracking, custody chain, quality checks, provenance, and food-safety', 'core',
    (SELECT id FROM business_capability WHERE name = 'Community & Partnerships' AND guild_key = 'community_partnerships'),
    'community_partnerships', 3, 'Community & Partnerships Guild', 'active'),
('Farmer Identity & Data Governance', 'Farmer profiles, credentials, KYC, consent, access audit, and portability', 'core',
    (SELECT id FROM business_capability WHERE name = 'Community & Partnerships' AND guild_key = 'community_partnerships'),
    'community_partnerships', 3, 'Community & Partnerships Guild', 'active')
ON CONFLICT (name, guild_key) DO UPDATE SET
    description = EXCLUDED.description,
    capability_type = EXCLUDED.capability_type,
    parent_id = EXCLUDED.parent_id,
    maturity_level = EXCLUDED.maturity_level,
    owner_role = EXCLUDED.owner_role,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================
-- Capability → Process mappings
-- ============================================================
INSERT INTO capability_process_map (capability_id, process_key, is_primary) VALUES
-- Technology Guild
((SELECT id FROM business_capability WHERE name = 'Event Delivery' AND guild_key = 'technology'), 'event_delivery', TRUE),
((SELECT id FROM business_capability WHERE name = 'Process Analytics' AND guild_key = 'technology'), 'process_analytics', TRUE),
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'agent_execution', TRUE),
((SELECT id FROM business_capability WHERE name = 'Data Publication' AND guild_key = 'technology'), 'data_publication', TRUE),
((SELECT id FROM business_capability WHERE name = 'Metric Governance' AND guild_key = 'technology'), 'metric_governance', TRUE),
((SELECT id FROM business_capability WHERE name = 'Systems Thinking' AND guild_key = 'technology'), 'systems_thinking', TRUE),
((SELECT id FROM business_capability WHERE name = 'Systems Thinking' AND guild_key = 'technology'), 'feedback_automation', FALSE),
-- Impact Guild
((SELECT id FROM business_capability WHERE name = 'Impact Verification' AND guild_key = 'impact'), 'impact_verification', TRUE),
((SELECT id FROM business_capability WHERE name = 'Pest & Disease Management' AND guild_key = 'impact'), 'pest_management', TRUE),
((SELECT id FROM business_capability WHERE name = 'Landscape & Biodiversity' AND guild_key = 'impact'), 'farm_operations', FALSE),
((SELECT id FROM business_capability WHERE name = 'Soil & Nutrient Management' AND guild_key = 'impact'), 'farm_operations', FALSE),
((SELECT id FROM business_capability WHERE name = 'Digital Twin Simulation' AND guild_key = 'impact'), 'performance_management', FALSE),
-- Communications Guild
((SELECT id FROM business_capability WHERE name = 'Reporting & Analytics' AND guild_key = 'communications'), 'reporting', TRUE),
((SELECT id FROM business_capability WHERE name = 'Extension & Training' AND guild_key = 'communications'), 'extension_training', TRUE),
((SELECT id FROM business_capability WHERE name = 'Stakeholder Feedback' AND guild_key = 'communications'), 'stakeholder_feedback', TRUE),
-- Governance Guild
((SELECT id FROM business_capability WHERE name = 'Decision Management' AND guild_key = 'governance'), 'decision_management', TRUE),
((SELECT id FROM business_capability WHERE name = 'Work Management' AND guild_key = 'governance'), 'work_management', TRUE),
((SELECT id FROM business_capability WHERE name = 'Process Governance' AND guild_key = 'governance'), 'process_governance', TRUE),
((SELECT id FROM business_capability WHERE name = 'Process Governance' AND guild_key = 'governance'), 'portfolio_management', FALSE),
((SELECT id FROM business_capability WHERE name = 'Emergency Response' AND guild_key = 'governance'), 'emergency_response', TRUE),
((SELECT id FROM business_capability WHERE name = 'Emergency Response' AND guild_key = 'governance'), 'escalation_management', FALSE),
-- Finance Guild
((SELECT id FROM business_capability WHERE name = 'Financial Planning' AND guild_key = 'finance'), 'financial_planning', TRUE),
((SELECT id FROM business_capability WHERE name = 'Carbon Lifecycle' AND guild_key = 'finance'), 'carbon_lifecycle', TRUE),
((SELECT id FROM business_capability WHERE name = 'Digital Finance' AND guild_key = 'finance'), 'digital_finance', TRUE),
((SELECT id FROM business_capability WHERE name = 'Marketplace Operations' AND guild_key = 'finance'), 'marketplace', TRUE),
-- Community & Partnerships Guild
((SELECT id FROM business_capability WHERE name = 'Farm Operations' AND guild_key = 'community_partnerships'), 'farm_operations', TRUE),
((SELECT id FROM business_capability WHERE name = 'Harvest & Yield Management' AND guild_key = 'community_partnerships'), 'harvest_management', TRUE),
((SELECT id FROM business_capability WHERE name = 'Cooperative Management' AND guild_key = 'community_partnerships'), 'cooperative_management', TRUE),
((SELECT id FROM business_capability WHERE name = 'Traceability' AND guild_key = 'community_partnerships'), 'traceability', TRUE),
((SELECT id FROM business_capability WHERE name = 'Farmer Identity & Data Governance' AND guild_key = 'community_partnerships'), 'stakeholder_feedback', FALSE)
ON CONFLICT (capability_id, process_key) DO NOTHING;

-- ============================================================
-- Capability → Service mappings
-- ============================================================
INSERT INTO capability_service_map (capability_id, service_name, is_primary) VALUES
-- Technology: Event Delivery
((SELECT id FROM business_capability WHERE name = 'Event Delivery' AND guild_key = 'technology'), 'events', TRUE),
((SELECT id FROM business_capability WHERE name = 'Event Delivery' AND guild_key = 'technology'), 'stream', FALSE),
((SELECT id FROM business_capability WHERE name = 'Event Delivery' AND guild_key = 'technology'), 'drivers', FALSE),
-- Technology: Process Analytics
((SELECT id FROM business_capability WHERE name = 'Process Analytics' AND guild_key = 'technology'), 'process_mining', TRUE),
((SELECT id FROM business_capability WHERE name = 'Process Analytics' AND guild_key = 'technology'), 'process_health', FALSE),
((SELECT id FROM business_capability WHERE name = 'Process Analytics' AND guild_key = 'technology'), 'process_gap', FALSE),
((SELECT id FROM business_capability WHERE name = 'Process Analytics' AND guild_key = 'technology'), 'process_costing', FALSE),
((SELECT id FROM business_capability WHERE name = 'Process Analytics' AND guild_key = 'technology'), 'process_simulation', FALSE),
((SELECT id FROM business_capability WHERE name = 'Process Analytics' AND guild_key = 'technology'), 'predictive_bpm', FALSE),
-- Technology: Agent Execution
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'ai_summary', TRUE),
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'cids_agent', FALSE),
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'feedback_agent', FALSE),
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'wellbeing_agent', FALSE),
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'resilience_agent', FALSE),
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'capital_efficiency_agent', FALSE),
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'commons_agent', FALSE),
((SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology'), 'gnh_agent', FALSE),
-- Technology: Data Publication
((SELECT id FROM business_capability WHERE name = 'Data Publication' AND guild_key = 'technology'), 'data_stream', TRUE),
((SELECT id FROM business_capability WHERE name = 'Data Publication' AND guild_key = 'technology'), 'data_module', FALSE),
((SELECT id FROM business_capability WHERE name = 'Data Publication' AND guild_key = 'technology'), 'iri', FALSE),
((SELECT id FROM business_capability WHERE name = 'Data Publication' AND guild_key = 'technology'), 'rdf', FALSE),
-- Technology: Metric Governance
((SELECT id FROM business_capability WHERE name = 'Metric Governance' AND guild_key = 'technology'), 'metrics', TRUE),
((SELECT id FROM business_capability WHERE name = 'Metric Governance' AND guild_key = 'technology'), 'prm_metrics', FALSE),
-- Impact: Impact Verification
((SELECT id FROM business_capability WHERE name = 'Impact Verification' AND guild_key = 'impact'), 'process_architecture', FALSE),
-- Impact: Pest & Disease Management
((SELECT id FROM business_capability WHERE name = 'Pest & Disease Management' AND guild_key = 'impact'), 'pest_management', TRUE),
-- Impact: Landscape & Biodiversity
((SELECT id FROM business_capability WHERE name = 'Landscape & Biodiversity' AND guild_key = 'impact'), 'landscape_conservation', TRUE),
((SELECT id FROM business_capability WHERE name = 'Landscape & Biodiversity' AND guild_key = 'impact'), 'pollinator_health', FALSE),
-- Impact: Soil & Nutrient Management
((SELECT id FROM business_capability WHERE name = 'Soil & Nutrient Management' AND guild_key = 'impact'), 'nutrient_budget', TRUE),
((SELECT id FROM business_capability WHERE name = 'Soil & Nutrient Management' AND guild_key = 'impact'), 'crop_rotation', FALSE),
-- Impact: Digital Twin Simulation
((SELECT id FROM business_capability WHERE name = 'Digital Twin Simulation' AND guild_key = 'impact'), 'digital_twin', TRUE),
-- Communications: Reporting & Analytics
((SELECT id FROM business_capability WHERE name = 'Reporting & Analytics' AND guild_key = 'communications'), 'report_generator', TRUE),
((SELECT id FROM business_capability WHERE name = 'Reporting & Analytics' AND guild_key = 'communications'), 'dataset_refresh', FALSE),
((SELECT id FROM business_capability WHERE name = 'Reporting & Analytics' AND guild_key = 'communications'), 'spreadsheet_bridge', FALSE),
-- Communications: Extension & Training
((SELECT id FROM business_capability WHERE name = 'Extension & Training' AND guild_key = 'communications'), 'extension', TRUE),
-- Communications: Stakeholder Feedback
((SELECT id FROM business_capability WHERE name = 'Stakeholder Feedback' AND guild_key = 'communications'), 'feedback_agent', TRUE),
-- Governance: Decision Management
((SELECT id FROM business_capability WHERE name = 'Decision Management' AND guild_key = 'governance'), 'security', TRUE),
((SELECT id FROM business_capability WHERE name = 'Decision Management' AND guild_key = 'governance'), 'scheduler', FALSE),
-- Governance: Work Management
((SELECT id FROM business_capability WHERE name = 'Work Management' AND guild_key = 'governance'), 'scheduler', TRUE),
-- Governance: Process Governance
((SELECT id FROM business_capability WHERE name = 'Process Governance' AND guild_key = 'governance'), 'service_catalog', TRUE),
((SELECT id FROM business_capability WHERE name = 'Process Governance' AND guild_key = 'governance'), 'process_model_sync', FALSE),
((SELECT id FROM business_capability WHERE name = 'Process Governance' AND guild_key = 'governance'), 'capability_map', FALSE),
((SELECT id FROM business_capability WHERE name = 'Process Governance' AND guild_key = 'governance'), 'strategy_map', FALSE),
((SELECT id FROM business_capability WHERE name = 'Process Governance' AND guild_key = 'governance'), 'vision_mission', FALSE),
((SELECT id FROM business_capability WHERE name = 'Process Governance' AND guild_key = 'governance'), 'value_stream_defs', FALSE),
-- Finance: Financial Planning
((SELECT id FROM business_capability WHERE name = 'Financial Planning' AND guild_key = 'finance'), 'report_generator', FALSE),
-- Finance: Carbon Lifecycle
((SELECT id FROM business_capability WHERE name = 'Carbon Lifecycle' AND guild_key = 'finance'), 'credit_class', TRUE),
((SELECT id FROM business_capability WHERE name = 'Carbon Lifecycle' AND guild_key = 'finance'), 'certificates', FALSE),
-- Finance: Digital Finance
((SELECT id FROM business_capability WHERE name = 'Digital Finance' AND guild_key = 'finance'), 'report_generator', FALSE),
-- Finance: Marketplace Operations
((SELECT id FROM business_capability WHERE name = 'Marketplace Operations' AND guild_key = 'finance'), 'marketplace', TRUE),
-- Community: Farm Operations
((SELECT id FROM business_capability WHERE name = 'Farm Operations' AND guild_key = 'community_partnerships'), 'sensor_ingester', TRUE),
((SELECT id FROM business_capability WHERE name = 'Farm Operations' AND guild_key = 'community_partnerships'), 'anomaly_detector', FALSE),
((SELECT id FROM business_capability WHERE name = 'Farm Operations' AND guild_key = 'community_partnerships'), 'weather_forecast', FALSE),
((SELECT id FROM business_capability WHERE name = 'Farm Operations' AND guild_key = 'community_partnerships'), 'remote_sensing_fetcher', FALSE),
-- Community: Harvest & Yield Management
((SELECT id FROM business_capability WHERE name = 'Harvest & Yield Management' AND guild_key = 'community_partnerships'), 'yield_monitoring', TRUE),
-- Community: Cooperative Management
((SELECT id FROM business_capability WHERE name = 'Cooperative Management' AND guild_key = 'community_partnerships'), 'cooperative', TRUE),
-- Community: Traceability
((SELECT id FROM business_capability WHERE name = 'Traceability' AND guild_key = 'community_partnerships'), 'traceability', TRUE),
-- Community: Farmer Identity & Data Governance
((SELECT id FROM business_capability WHERE name = 'Farmer Identity & Data Governance' AND guild_key = 'community_partnerships'), 'farmer_identity', TRUE),
((SELECT id FROM business_capability WHERE name = 'Farmer Identity & Data Governance' AND guild_key = 'community_partnerships'), 'data_governance', FALSE),
-- Core infrastructure services
((SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'), 'gateway', TRUE),
((SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'), 'grpc', FALSE),
((SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'), 'metadata_api', FALSE),
((SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'), 'federation', FALSE),
((SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'), 'core', FALSE)
ON CONFLICT (capability_id, service_name) DO NOTHING;

-- ============================================================
-- Platform Vision & Mission
-- ============================================================
INSERT INTO vision_mission (entity_type, entity_id, statement_type, statement_text, effective_date, status, approved_by, approved_at) VALUES
('platform', NULL, 'vision',
    'A regenerative farm operating system that makes every farm comparable, fundable, governable, and verifiable — enabling communities to build wealth from ecological stewardship.',
    '2026-01-01', 'approved', 'platform', NOW()),
('platform', NULL, 'mission',
    'To provide open-source digital infrastructure that connects regenerative farming practices to measurable impact, transparent governance, and fair market access — empowering smallholder farmers to thrive as stewards of natural capital.',
    '2026-01-01', 'approved', 'platform', NOW()),
('platform', NULL, 'values',
    'Regeneration over extraction. Community over individual. Transparency over opacity. Open source over proprietary. Measurable impact over intention.',
    '2026-01-01', 'approved', 'platform', NOW())
ON CONFLICT DO NOTHING;

-- ============================================================
-- Platform Strategy Map (Balanced Scorecard)
-- ============================================================
INSERT INTO strategy_map (
    entity_type, entity_id, perspective, strategic_theme, statement,
    status, metadata
) VALUES
('platform', NULL, 'financial', 'Regenerative Value',
 'Build durable and diversified revenue that rewards ecological stewardship.',
 'not_started', '{"source":"kokonut business architecture"}'::jsonb),
('platform', NULL, 'customer', 'Farmer and Stakeholder Value',
 'Deliver trusted evidence, fair market access, and useful intelligence to every stakeholder.',
 'not_started', '{"source":"kokonut business architecture"}'::jsonb),
('platform', NULL, 'internal_process', 'Governed Operational Excellence',
 'Operate transparent, measurable, human-governed value streams with continuously improving flow.',
 'not_started', '{"source":"kokonut business architecture"}'::jsonb),
('platform', NULL, 'learning_growth', 'Open Regenerative Capacity',
 'Grow community, Guild, data, and open-source capabilities faster than platform complexity.',
 'not_started', '{"source":"kokonut business architecture"}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO strategy_capability_map (
    strategy_map_id, capability_id, contribution_type, expected_impact
) VALUES
((SELECT id FROM strategy_map WHERE entity_type = 'platform' AND perspective = 'financial'),
 (SELECT id FROM business_capability WHERE name = 'Financial Operations' AND guild_key = 'finance'),
 'primary', 'Build diversified and governed regenerative revenue'),
((SELECT id FROM strategy_map WHERE entity_type = 'platform' AND perspective = 'customer'),
 (SELECT id FROM business_capability WHERE name = 'Community & Partnerships' AND guild_key = 'community_partnerships'),
 'primary', 'Ground platform value in farmer and stakeholder needs'),
((SELECT id FROM strategy_map WHERE entity_type = 'platform' AND perspective = 'customer'),
 (SELECT id FROM business_capability WHERE name = 'Communications & Content' AND guild_key = 'communications'),
 'enabling', 'Translate governed evidence into useful stakeholder communication'),
((SELECT id FROM strategy_map WHERE entity_type = 'platform' AND perspective = 'internal_process'),
 (SELECT id FROM business_capability WHERE name = 'Platform Governance' AND guild_key = 'governance'),
 'primary', 'Preserve human approval, accountability, and process integrity'),
((SELECT id FROM strategy_map WHERE entity_type = 'platform' AND perspective = 'internal_process'),
 (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'),
 'enabling', 'Automate durable flow without weakening governance'),
((SELECT id FROM strategy_map WHERE entity_type = 'platform' AND perspective = 'learning_growth'),
 (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology'),
 'primary', 'Grow reusable open-source and data capabilities'),
((SELECT id FROM strategy_map WHERE entity_type = 'platform' AND perspective = 'learning_growth'),
 (SELECT id FROM business_capability WHERE name = 'Community & Partnerships' AND guild_key = 'community_partnerships'),
 'enabling', 'Grow local knowledge and execution capacity')
ON CONFLICT (strategy_map_id, capability_id) DO UPDATE SET
    contribution_type = EXCLUDED.contribution_type,
    expected_impact = EXCLUDED.expected_impact;

-- ============================================================
-- Value Stream Definitions
-- ============================================================

-- VS1: Farm-to-Market
INSERT INTO value_stream_definition (name, description, stakeholder_type, trigger_event, end_state, owner_role, status) VALUES
('Farm-to-Market', 'End-to-end value stream from farm activity recording through harvest to market sale',
    'farmer', 'Farm activity recorded', 'Revenue received from buyer', 'Community & Partnerships Guild', 'active')
ON CONFLICT (name) DO NOTHING;

INSERT INTO value_stream_stage (stream_id, name, description, sequence_order, process_key, target_lead_time_hours, target_fty_pct) VALUES
((SELECT id FROM value_stream_definition WHERE name = 'Farm-to-Market'), 'Activity Recording', 'Farm activity logged with sensor data', 1, 'farm_operations', 1, 95),
((SELECT id FROM value_stream_definition WHERE name = 'Farm-to-Market'), 'Growth & Monitoring', 'Crop growth with precision irrigation and pest management', 2, 'farm_operations', 720, 90),
((SELECT id FROM value_stream_definition WHERE name = 'Farm-to-Market'), 'Harvest', 'Harvest event recorded and verified', 3, 'harvest_management', 24, 90),
((SELECT id FROM value_stream_definition WHERE name = 'Farm-to-Market'), 'Traceability', 'Batch tracking, custody chain, quality check', 4, 'traceability', 48, 85),
((SELECT id FROM value_stream_definition WHERE name = 'Farm-to-Market'), 'Market Listing', 'Product listed on marketplace with price', 5, 'marketplace', 12, 95),
((SELECT id FROM value_stream_definition WHERE name = 'Farm-to-Market'), 'Sale & Delivery', 'Order placed, delivered, and payment received', 6, 'marketplace', 72, 90)
ON CONFLICT (stream_id, sequence_order) DO NOTHING;

-- VS2: Carbon Credit Lifecycle
INSERT INTO value_stream_definition (name, description, stakeholder_type, trigger_event, end_state, owner_role, status) VALUES
('Carbon Credit Lifecycle', 'From carbon sequestration measurement through credit issuance to retirement',
    'investor', 'Soil carbon measured', 'Credit retired with certificate', 'Finance Guild', 'active')
ON CONFLICT (name) DO NOTHING;

INSERT INTO value_stream_stage (stream_id, name, description, sequence_order, process_key, target_lead_time_hours, target_fty_pct) VALUES
((SELECT id FROM value_stream_definition WHERE name = 'Carbon Credit Lifecycle'), 'Measurement', 'Soil carbon and sequestration metrics computed', 1, 'metric_governance', 24, 90),
((SELECT id FROM value_stream_definition WHERE name = 'Carbon Credit Lifecycle'), 'Verification', 'Metric verification and impact claim creation', 2, 'impact_verification', 168, 85),
((SELECT id FROM value_stream_definition WHERE name = 'Carbon Credit Lifecycle'), 'Issuance', 'Credit batch created and issued on-chain', 3, 'carbon_lifecycle', 72, 90),
((SELECT id FROM value_stream_definition WHERE name = 'Carbon Credit Lifecycle'), 'Trading', 'Credit listed and sold on marketplace', 4, 'marketplace', 240, 80),
((SELECT id FROM value_stream_definition WHERE name = 'Carbon Credit Lifecycle'), 'Retirement', 'Credit retired with certificate generation', 5, 'carbon_lifecycle', 24, 95)
ON CONFLICT (stream_id, sequence_order) DO NOTHING;

-- VS3: Data-to-Impact
INSERT INTO value_stream_definition (name, description, stakeholder_type, trigger_event, end_state, owner_role, status) VALUES
('Data-to-Impact', 'From raw sensor data through analysis to published impact claims',
    'regulator', 'Sensor data ingested', 'Impact claim published with attestation', 'Impact Guild', 'active')
ON CONFLICT (name) DO NOTHING;

INSERT INTO value_stream_stage (stream_id, name, description, sequence_order, process_key, target_lead_time_hours, target_fty_pct) VALUES
((SELECT id FROM value_stream_definition WHERE name = 'Data-to-Impact'), 'Ingestion', 'Sensor data collected and validated', 1, 'data_publication', 1, 95),
((SELECT id FROM value_stream_definition WHERE name = 'Data-to-Impact'), 'Processing', 'Stream processing, anomaly detection, windowing', 2, 'event_delivery', 2, 90),
((SELECT id FROM value_stream_definition WHERE name = 'Data-to-Impact'), 'Analysis', 'Metric computation, CRISP scoring, trend analysis', 3, 'metric_governance', 6, 85),
((SELECT id FROM value_stream_definition WHERE name = 'Data-to-Impact'), 'Publication', 'Data stream post created and reviewed', 4, 'data_publication', 24, 90),
((SELECT id FROM value_stream_definition WHERE name = 'Data-to-Impact'), 'Impact Claim', 'Impact claim submitted with evidence', 5, 'impact_verification', 72, 80),
((SELECT id FROM value_stream_definition WHERE name = 'Data-to-Impact'), 'Attestation', 'On-chain attestation via EAS', 6, 'impact_verification', 24, 90)
ON CONFLICT (stream_id, sequence_order) DO NOTHING;

-- VS4: Stakeholder Engagement
INSERT INTO value_stream_definition (name, description, stakeholder_type, trigger_event, end_state, owner_role, status) VALUES
('Stakeholder Engagement', 'From initial contact through onboarding to active participation',
    'community', 'Stakeholder identified', 'Active participant with governance rights', 'Community & Partnerships Guild', 'active')
ON CONFLICT (name) DO NOTHING;

INSERT INTO value_stream_stage (stream_id, name, description, sequence_order, process_key, target_lead_time_hours, target_fty_pct) VALUES
((SELECT id FROM value_stream_definition WHERE name = 'Stakeholder Engagement'), 'Identification', 'Stakeholder public created with influence/interest mapping', 1, 'stakeholder_feedback', 24, 95),
((SELECT id FROM value_stream_definition WHERE name = 'Stakeholder Engagement'), 'Onboarding', 'Farmer identity created, KYC completed', 2, 'extension_training', 168, 85),
((SELECT id FROM value_stream_definition WHERE name = 'Stakeholder Engagement'), 'Training', 'Extension modules completed, peer group joined', 3, 'extension_training', 336, 80),
((SELECT id FROM value_stream_definition WHERE name = 'Stakeholder Engagement'), 'Participation', 'Feedback submitted, data shared, governance participated', 4, 'stakeholder_feedback', 720, 75),
((SELECT id FROM value_stream_definition WHERE name = 'Stakeholder Engagement'), 'Active Member', 'Cooperative member with decision rights', 5, 'cooperative_management', 2160, 70)
ON CONFLICT (stream_id, sequence_order) DO NOTHING;
