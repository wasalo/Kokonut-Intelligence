-- ============================================================
-- 099_coconut_syntropic_template.sql — Coconut Syntropic Template
-- ============================================================
-- Coconut-specific syntropic farm template for multi-farm deployment.

INSERT INTO farm_template (
    id, template_name, template_type, description, version,
    default_zones,
    default_governance_mechanism,
    default_governance_config,
    default_token_allocation,
    default_public_goods_allocation_pct,
    default_redistribution_config,
    default_impact_frameworks,
    default_principles,
    suggested_farm_type,
    suggested_climate_zone,
    suggested_min_area_m2,
    suggested_max_area_m2,
    author, tags, status, source_system, source_id
) VALUES (
    'a0000000-0000-0000-0000-000000005320',
    'Coconut Syntropic',
    'syntropic',
    'Coconut-focused syntropic farm template with multi-strata production, integrated livestock, and bio-input loop. Optimized for tropical coconut-growing regions with intercrop companion species.',
    '1.0',
    '[
        {"zone_type":"coconut_grove","name":"Coconut Production Grove","strata_layer":"canopy","area_m2":12000,"description":"Primary coconut planting zone with multi-strata intercrops"},
        {"zone_type":"syntropic_plot","name":"Syntropic Intercrop Beds","strata_layer":"sub_canopy","area_m2":4000,"description":"Companion species beds: cacao, banana, yam, legumes"},
        {"zone_type":"nursery","name":"Coconut Nursery","strata_layer":"regeneration","area_m2":800,"description":"Seedling production and propagation area"},
        {"zone_type":"biofactory","name":"Bio-Input Production","strata_layer":"decomposer","area_m2":1200,"description":"Compost, vermicompost, biochar, and biofertilizer production"},
        {"zone_type":"poultry","name":"Poultry Integration","strata_layer":"herbaceous","area_m2":500,"description":"Free-range poultry for pest control and fertilization"},
        {"zone_type":"processing","name":"Post-Harvest Processing","strata_layer":"processing","area_m2":600,"description":"Copra drying, coconut oil extraction, packaging"}
    ]'::jsonb,
    'moloch_dao',
    '{"decision_method":"consensus","voting_method":"one_person_one_vote","community_veto_enabled":true}'::jsonb,
    '65% farm operators, 20% DAO/community contributors, 10% public goods reserve, 5% reserve',
    10.000,
    '{"commons_allocation_pct":10.0,"operator_allocation_pct":65.0,"local_cooperative_allocation_pct":10.0,"digital_commons_allocation_pct":5.0,"reserve_allocation_pct":5.0}'::jsonb,
    '{kokonut_framework, ebf, sdg, crisp, regeneration_principles}',
    '{soil_protection, living_cover, biodiversity, animal_integration, organic_inputs}',
    'syntropic',
    'tropical',
    10000.00,
    50000.00,
    'Kokonut Collective',
    '{coconut, syntropic, tropical, regenerative, cooperative, intercrop}',
    'published',
    'seed',
    'template-coconut-syntropic'
) ON CONFLICT (id) DO UPDATE SET
    template_name = EXCLUDED.template_name,
    description = EXCLUDED.description,
    default_zones = EXCLUDED.default_zones,
    default_principles = EXCLUDED.default_principles,
    status = EXCLUDED.status;
