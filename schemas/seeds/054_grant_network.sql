-- ============================================================
-- 054_grant_network.sql — Seeds: metrics, Adelphi pilot data, grant application template
-- ============================================================

-- New metric definitions
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('grant_funding_rate', 'Grant Funding Rate', 'Percentage of grant applications that were funded.', 'count(funded applications) / count(total applications) * 100', ARRAY['grant_application_history'], 'Use published grant application records.', 'Exclude draft or rejected records.', 'percentage', 'numeric', 'Finance Guild', 1, 'annually', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['grant_management', 'financial_sustainability'], 'Supersede through metric_version before changing public interpretation.'),
('network_species_diversity', 'Network Species Diversity', 'Total unique species observed across all farms in the network.', 'count(distinct species_name) from species_observation across network farms', ARRAY['species_observation', 'network_membership'], 'Use published species observations from network member farms.', 'Exclude observations without valid species_name.', 'count', 'integer', 'Ecology Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['network_diversity', 'biodiversity'], 'Supersede through metric_version before changing public interpretation.')
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

-- Adelphi pilot: grant application history
INSERT INTO grant_application_history (
    id, location_id, grant_name, grantor,
    application_date, application_status, grant_cycle, grant_cycle_number,
    is_returning_applicant, amount_requested, amount_awarded, currency,
    funding_focus, ecological_metrics_submitted, community_partnerships,
    geographic_region, notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005410',
 'a0000000-0000-0000-0000-000000000001',
 'Ma Earth Land Regenerators Grant',
 'Ma Earth',
 '2025-06-01', 'funded', '2025-Q2', 1,
 FALSE, 25000.00, 25000.00, 'USD',
 'Syntropic farm establishment, ecological monitoring, community training',
 '{"carbon_sequestration": "2.8 tCO2e/ha", "species_count": 29, "soil_carbon_delta": "+0.3 t/ha", "tree_survival": "91.6%"}'::jsonb,
 ARRAY['Kokonut Collective', 'Local Cooperatives', 'Community Farmers'],
 'Caribbean',
 'First grant application. Established Adelphi as proof-of-concept syntropic farm.',
 'published', 'pilot_seed', 'adelphi-grant-ma-earth',
 '{"record_type":"grant_application_history","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005411',
 'a0000000-0000-0000-0000-000000000001',
 'Regenerative Agriculture Innovation Fund',
 'Global Green Fund',
 '2026-01-15', 'submitted', '2026-Q1', 2,
 TRUE, 50000.00, NULL, 'USD',
 'Scale syntropic model to 3 new sites, publish ecological evidence, train 50 community members',
 '{"carbon_sequestration": "5.6 tCO2e/ha projected", "species_count": 45 target", "soil_carbon_delta": "+0.8 t/ha target"}'::jsonb,
 ARRAY['Kokonut Collective', 'Regional Cooperatives', 'University Research Partners'],
 'Caribbean',
 'Returning applicant. Proposal builds on Adelphi pilot success. Demonstrates replication readiness.',
 'published', 'pilot_seed', 'adelphi-grant-ggf',
 '{"record_type":"grant_application_history","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    grant_name = EXCLUDED.grant_name,
    application_status = EXCLUDED.application_status,
    updated_at = NOW();

-- Update farm_registry_record with grant history
UPDATE farm_registry_record SET
    returning_applicant = TRUE,
    grant_count = 2,
    total_grants_received = 25000.00
WHERE id = 'a0000000-0000-0000-0000-000000000500';

-- Adelphi pilot: regional chapter
INSERT INTO regional_chapter (
    id, chapter_name, chapter_key, description,
    geographic_region, country, region, chapter_type,
    founding_date, status, notes,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005420',
 'Caribbean Syntropic Network',
 'caribbean-syntropic',
 'Regional network of syntropic farms across the Caribbean, focused on regenerative agriculture, food sovereignty, and climate resilience.',
 'Caribbean', 'Dominican Republic', 'Antilles', 'regional',
 '2025-09-01', 'active',
 'Founded with Adelphi as the first demonstration site. Expanding to Jamaica, Haiti, and Puerto Rico.',
 'pilot_seed', 'adelphi-chapter-caribbean',
 '{"record_type":"regional_chapter","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    chapter_name = EXCLUDED.chapter_name,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Adelphi pilot: network membership
INSERT INTO network_membership (
    id, location_id, chapter_id, membership_type, join_date, role,
    contribution_focus, status, notes,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005430',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005420',
 'founding_member', '2025-09-01', 'demonstration_site',
 'Proof-of-concept for syntropic farming in Caribbean climate. Hosts training programs for regional farmers.',
 'active',
 'Adelphi is the founding demonstration site of the Caribbean Syntropic Network.',
 'pilot_seed', 'adelphi-membership-caribbean',
 '{"record_type":"network_membership","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    role = EXCLUDED.role,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Grant Application Template (for new farms applying to grants)
INSERT INTO farm_template (
    id, template_name, template_type, description, version,
    default_zones, default_governance_mechanism, default_governance_config,
    default_token_allocation, default_public_goods_allocation_pct, default_redistribution_config,
    default_impact_frameworks, default_principles,
    suggested_farm_type, suggested_climate_zone, suggested_min_area_m2, suggested_max_area_m2,
    author, tags, status, source_system, source_id, source_raw
) VALUES (
 'a0000000-0000-0000-0000-000000005440',
 'Grant Application Template',
 'regenerative',
 'Pre-configured template for applying to regenerative agriculture grants. Includes all data fields funders typically require: land security, ecological metrics, community engagement, on-chain/off-chain flow, and impact framework.',
 '1.0',
 '[
    {"zone_type": "syntropic_plot", "name": "Production Zone", "description": "Primary production area with multi-strata crops"},
    {"zone_type": "nursery", "name": "Nursery", "description": "Seedling production and propagation"},
    {"zone_type": "biofactory", "name": "Biofactory", "description": "On-farm input production (compost, vermicompost, biopesticides)"}
 ]'::jsonb,
 'moloch_dao',
 '{"decision_method": "consensus", "community_veto_enabled": true}'::jsonb,
 '70% operators, 20% community, 10% public goods',
 10.000,
 '{"commons_allocation_pct": 10.0, "operator_allocation_pct": 70.0}'::jsonb,
 ARRAY['kokonut_framework', 'ebf', 'sdg'],
 ARRAY['soil_protection', 'living_cover', 'biodiversity'],
 'regenerative', NULL, 1000.00, 50000.00,
 'Kokonut Collective',
 ARRAY['grant', 'application', 'template', 'regenerative', 'funder-ready'],
 'published',
 'pilot_seed', 'template-grant-application',
 '{"record_type":"farm_template","privacy":"public_summary","purpose":"grant_application"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    template_name = EXCLUDED.template_name,
    description = EXCLUDED.description,
    updated_at = NOW();
