-- ============================================================
-- 053_configurable_containers.sql — Seeds: metrics, Adelphi pilot data
-- ============================================================

-- New metric definitions
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('objective_completion_pct', 'Objective Completion %', 'Average progress across all active objectives.', 'avg(progress_pct) from objective where status in approved/in_progress', ARRAY['objective'], 'Use approved or in_progress objectives with progress data.', 'Exclude objectives without target_value.', 'percentage', 'numeric', 'Governance Guild', 1, 'monthly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['objectives', 'governance'], 'Supersede through metric_version before changing public interpretation.'),
('needs_resolution_rate', 'Needs Resolution Rate', 'Percentage of identified needs that have been resolved.', 'count(resolved needs) / count(total needs) * 100', ARRAY['needs_assessment'], 'Use published needs assessments.', 'Exclude draft or rejected records.', 'percentage', 'numeric', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['needs_assessment', 'governance'], 'Supersede through metric_version before changing public interpretation.')
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

-- Adelphi pilot: farm template (syntropic model)
INSERT INTO farm_template (
    id, template_name, template_type, description, version,
    default_zones, default_governance_mechanism, default_governance_config,
    default_token_allocation, default_public_goods_allocation_pct, default_redistribution_config,
    default_impact_frameworks, default_principles,
    suggested_farm_type, suggested_climate_zone, suggested_min_area_m2, suggested_max_area_m2,
    author, tags, status, source_system, source_id, source_raw
) VALUES (
 'a0000000-0000-0000-0000-000000005310',
 'Kokonut Syntropic Farm Template',
 'syntropic',
 'Standard syntropic farm configuration with multi-strata production, biofactory loop, and integrated poultry. Based on Adelphi pilot model.',
 '1.0',
 '[
    {"zone_type": "syntropic_plot", "name": "Syntropic Production Beds", "strata_layer": "canopy", "area_m2": 7838, "description": "Multi-strata syntropic production with coconut, passion fruit, and intercrops"},
    {"zone_type": "agroforestry", "name": "Agroforestry Corridor", "strata_layer": "sub_canopy", "area_m2": 4500, "description": "N-fixer support species corridor connecting production zones"},
    {"zone_type": "biofactory", "name": "Nursery and Biofactory", "strata_layer": "decomposer", "area_m2": 1000, "description": "Vermicompost, compost tea, and seedling nursery"},
    {"zone_type": "poultry", "name": "Poultry Integration Loop", "strata_layer": "herbaceous", "area_m2": 500, "description": "Free-range chickens for pest control and fertility"}
 ]'::jsonb,
 'moloch_dao',
 '{"decision_method": "consensus", "voting_method": "one_person_one_vote", "community_veto_enabled": true}'::jsonb,
 '70% farm operators, 20% DAO/community contributors, 10% public goods reserve',
 10.000,
 '{"commons_allocation_pct": 10.0, "operator_allocation_pct": 70.0, "local_cooperative_allocation_pct": 10.0, "digital_commons_allocation_pct": 5.0, "reserve_allocation_pct": 5.0}'::jsonb,
 ARRAY['kokonut_framework', 'ebf', 'sdg', 'regeneration_principles'],
 ARRAY['soil_protection', 'living_cover', 'biodiversity', 'animal_integration', 'organic_inputs'],
 'syntropic', 'tropical', 5000.00, 50000.00,
 'Kokonut Collective',
 ARRAY['syntropic', 'tropical', 'community', 'regenerative', 'pilot'],
 'published',
 'pilot_seed', 'adelphi-template-syntropic',
 '{"record_type":"farm_template","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    template_name = EXCLUDED.template_name,
    default_zones = EXCLUDED.default_zones,
    updated_at = NOW();

-- Adelphi pilot: farm specification (instantiated from template)
INSERT INTO farm_specification (
    id, location_id, template_id, spec_name, version,
    zones, governance, token_economics, impact_config, regeneration_principles,
    is_override, validation_status, applied_at,
    status, source_system, source_id, source_raw
) VALUES (
 'a0000000-0000-0000-0000-000000005320',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005310',
 'Adelphi Syntropic Farm Specification',
 '1.0',
 '[
    {"zone_type": "syntropic_plot", "name": "Syntropic Production Beds", "strata_layer": "canopy", "area_m2": 7838, "zone_key": "adelphi-syntropic-beds"},
    {"zone_type": "agroforestry", "name": "Agroforestry Corridor", "strata_layer": "sub_canopy", "area_m2": 4500, "zone_key": "adelphi-agroforestry-corridor"},
    {"zone_type": "biofactory", "name": "Nursery and Biofactory", "strata_layer": "decomposer", "area_m2": 1000, "zone_key": "adelphi-nursery-biofactory"},
    {"zone_type": "poultry", "name": "Poultry Integration Loop", "strata_layer": "herbaceous", "area_m2": 500, "zone_key": "adelphi-poultry-loop"}
 ]'::jsonb,
 '{"mechanism_name": "Adelphi Community Governance", "decision_method": "consensus", "governance_level": "farm", "community_veto_rights": "Full veto on resource allocation and land use changes"}'::jsonb,
 '{"token_allocation": "70% farm operators, 20% DAO/community contributors, 10% public goods reserve", "public_goods_allocation_pct": 10.0}'::jsonb,
 '{"frameworks": ["kokonut_framework", "ebf", "sdg"], "impact_mappings_count": 12, "ebf_scorecard_active": true}'::jsonb,
 '{"principles": ["soil_protection", "living_cover", "biodiversity", "animal_integration", "organic_inputs"], "practice_scores": {"soil_protection": 4, "living_cover": 5, "biodiversity": 4, "animal_integration": 3, "organic_inputs": 5}}'::jsonb,
 FALSE, 'valid', '2025-10-01',
 'published', 'pilot_seed', 'adelphi-spec-syntropic',
 '{"record_type":"farm_specification","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    zones = EXCLUDED.zones,
    governance = EXCLUDED.governance,
    updated_at = NOW();

-- Adelphi pilot: needs assessments
INSERT INTO needs_assessment (
    id, location_id, need_category, need_name, description,
    severity, urgency, affected_stakeholder_groups, affected_count,
    current_state, desired_state, mitigation_plan, mitigation_status,
    target_resolution_date, assessor, assessment_date, notes,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005330',
 'a0000000-0000-0000-0000-000000000001',
 'infrastructure', 'Water Storage Capacity',
 'Current water storage limited to 5000L tank. Insufficient for dry season irrigation of 2.5ha syntropic beds.',
 'high', 'high',
 ARRAY['farm_operators', 'community'], 5,
 '5000L storage capacity, manual irrigation during dry season',
 '15000L storage capacity with gravity-fed drip irrigation',
 'Install 2 additional 5000L tanks and gravity-fed drip system for syntropic beds',
 'in_progress', '2026-06-01',
 'Kokonut Collective', '2025-10-01',
 'Water storage identified as critical bottleneck for dry season production continuity.',
 'published', 'pilot_seed', 'adelphi-need-water',
 '{"record_type":"needs_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005331',
 'a0000000-0000-0000-0000-000000000001',
 'capacity_building', 'Bio-input Production Skills',
 'Field workers need training on vermicompost production, compost tea brewing, and biopesticide preparation.',
 'medium', 'medium',
 ARRAY['field_workers'], 8,
 'Workers can apply purchased inputs but cannot produce on-farm bio-inputs',
 'Workers independently produce vermicompost, compost tea, biopesticides, and seedling nursery products',
 'Hands-on training program: 3 sessions x 4 hours each, with follow-up mentoring',
 'in_progress', '2026-03-01',
 'Kokonut Collective', '2025-10-15',
 'Bio-input production is core to syntropic model. Training essential for reducing input costs.',
 'published', 'pilot_seed', 'adelphi-need-bioinput',
 '{"record_type":"needs_assessment","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005332',
 'a0000000-0000-0000-0000-000000000001',
 'market', 'Local Market Access',
 'No established buyer relationships for premium organic produce. Relying on farm-gate sales at sub-optimal prices.',
 'medium', 'medium',
 ARRAY['farm_operators', 'community'], 12,
 'Farm-gate sales only, 40% of potential revenue captured',
 'Establish 3+ buyer relationships (restaurants, retailers, cooperatives) at premium organic prices',
 'Market mapping, buyer outreach, quality certification, and supply chain development',
 'planned', '2026-09-01',
 'Kokonut Collective', '2025-10-01',
 'Market access is key to financial sustainability. Premium pricing justified by organic/syntropic certification.',
 'published', 'pilot_seed', 'adelphi-need-market',
 '{"record_type":"needs_assessment","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    need_name = EXCLUDED.need_name,
    severity = EXCLUDED.severity,
    mitigation_status = EXCLUDED.mitigation_status,
    updated_at = NOW();

-- Adelphi pilot: stakeholder aspirations
INSERT INTO stakeholder_aspiration (
    id, location_id, aspiration_name, description,
    aspiration_category, priority, stakeholder_group,
    desired_outcome, success_criteria, timeline_months, status,
    notes, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005340',
 'a0000000-0000-0000-0000-000000000001',
 'Become a Regional Model for Syntropic Agriculture',
 'Adelphi should demonstrate that syntropic farming is economically viable and ecologically regenerative, serving as a replication model for the Caribbean region.',
 'ecological', 'high', 'farm_operators',
 'Recognized regional model with 3+ replication sites and published evidence',
 'At least 2 farms replicating the Adelphi model with verified outcomes within 3 years',
 36, 'approved',
 'The Adelphi pilot is designed as a proof-of-concept for the Kokonut Network model.',
 'pilot_seed', 'adelphi-aspiration-model',
 '{"record_type":"stakeholder_aspiration","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005341',
 'a0000000-0000-0000-0000-000000000001',
 'Achieve Financial Self-Sufficiency Within 3 Years',
 'The farm should cover all operating costs from revenue within 3 years, reducing grant dependency to below 20%.',
 'financial', 'high', 'farm_operators',
 'Self-sustaining operations with surplus for reinvestment and public goods',
 'Annual revenue > annual costs for 2 consecutive years; grant dependency < 20%',
 36, 'approved',
 'Financial sustainability is critical for long-term viability and scaling.',
 'pilot_seed', 'adelphi-aspiration-financial',
 '{"record_type":"stakeholder_aspiration","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005342',
 'a0000000-0000-0000-0000-000000000001',
 'Train 50 Community Members in Regenerative Practices',
 'Build local capacity by training community members in syntropic agriculture, bio-input production, and organic certification.',
 'capacity', 'medium', 'community',
 'Trained community members who can establish and manage their own syntropic farms',
 '50 individuals complete training program with measured improvement in best practices adoption',
 24, 'approved',
 'Training is essential for scaling and community ownership.',
 'pilot_seed', 'adelphi-aspiration-training',
 '{"record_type":"stakeholder_aspiration","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    aspiration_name = EXCLUDED.aspiration_name,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Adelphi pilot: hierarchical objectives
INSERT INTO objective (
    id, location_id, parent_id, objective_name, description,
    objective_type, category, target_value, current_value, unit, target_date,
    owner, priority, status, notes,
    source_system, source_id, source_raw
) VALUES
-- Strategic objectives (top level)
('a0000000-0000-0000-0000-000000005350',
 'a0000000-0000-0000-0000-000000000001', NULL,
 'Establish Adelphi as Proof-of-Concept Farm',
 'Complete 2 full production cycles with verified ecological and financial outcomes.',
 'strategic', 'operational', 2.0, 1.0, 'cycles', '2027-03-01',
 'Farm Manager', 'critical', 'in_progress',
 'First cycle completed (Oct 2025 - Mar 2026). Second cycle in progress.',
 'pilot_seed', 'adelphi-obj-proof-of-concept',
 '{"record_type":"objective","privacy":"public_summary"}'::jsonb),
-- Operational objectives (children)
('a0000000-0000-0000-0000-000000005351',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005350',
 'Achieve 80% Soil Organic Matter Increase',
 'Increase soil organic matter from baseline by 80% over 2 years through compost, biochar, and leaf litter applications.',
 'operational', 'ecological', 80.0, 45.0, 'percent', '2027-10-01',
 'Agronomist', 'high', 'in_progress',
 'Current increase: 45% (from 2.2% to 3.3% SOM). On track for target.',
 'pilot_seed', 'adelphi-obj-soil-organic',
 '{"record_type":"objective","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005352',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005350',
 'Train 20 Field Workers in Bio-input Production',
 'Complete bio-input production training for all field workers within 12 months.',
 'operational', 'capacity', 20.0, 4.0, 'workers', '2026-10-01',
 'Training Coordinator', 'high', 'in_progress',
 '4 workers trained (Maria, Carlos, Ana, Luis). 16 remaining.',
 'pilot_seed', 'adelphi-obj-training',
 '{"record_type":"objective","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005353',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005350',
 'Establish 3 Buyer Relationships',
 'Secure supply agreements with at least 3 premium buyers for organic produce.',
 'operational', 'financial', 3.0, 1.0, 'buyers', '2026-12-01',
 'Farm Manager', 'medium', 'in_progress',
 '1 buyer relationship established (local restaurant). 2 more in negotiation.',
 'pilot_seed', 'adelphi-obj-buyers',
 '{"record_type":"objective","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005354',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005350',
 'Achieve 100 Tree Survival Rate',
 'Maintain 100% survival rate for all planted trees through first year.',
 'operational', 'ecological', 100.0, 91.6, 'percent', '2026-10-01',
 'Field Coordinator', 'medium', 'in_progress',
 'Current survival rate: 91.6% (141 of 154 trees surviving). Replacements planted for 13 losses.',
 'pilot_seed', 'adelphi-obj-tree-survival',
 '{"record_type":"objective","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    current_value = EXCLUDED.current_value,
    status = EXCLUDED.status,
    updated_at = NOW();
