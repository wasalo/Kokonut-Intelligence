-- ============================================================
-- 026_pilot_farm_onboarding.sql — Adelphi onboarding/profile fields
-- ============================================================

UPDATE farm
SET logo_url = 'https://hub.kokonut.network/projects/41/logo.png',
    traditional_name = 'Finca Adelphi',
    languages = ARRAY['en', 'es'],
    global_standard_certifications = ARRAY['syntropic_agriculture', 'regenerative_organic_candidate'],
    economic_sectors = ARRAY['agriculture', 'agroforestry', 'bioinputs', 'public_goods'],
    credits_registries = ARRAY['celo_eas', 'regen_registry_candidate'],
    data_privacy_status = 'public_summary_private_evidence',
    data_privacy_standard = 'kokonut-public-metadata-private-evidence-v1',
    data_privacy_criteria = '{
        "public": ["farm profile", "aggregate metrics", "attestation UIDs", "CIDs", "hashes"],
        "private": ["raw evidence files", "PII", "precise sensitive household survey responses"],
        "requirements_met": ["no private evidence payloads in public metadata", "public views require verified or published registry record"]
    }'::jsonb,
    updated_at = NOW()
WHERE id = 'a0000000-0000-0000-0000-000000000010';

UPDATE farm_registry_record
SET daoip5_project_id = 'daoip-5:Kokonut:project:kokonut-adelphi',
    projects_uri = 'https://hub.kokonut.network/projects/41/daoip5/projects.json',
    content_uri = 'https://hub.kokonut.network/projects/41',
    image_url = 'https://hub.kokonut.network/projects/41/logo.png',
    cover_image_url = 'https://hub.kokonut.network/projects/41/cover.png',
    license_uri = 'https://creativecommons.org/publicdomain/zero/1.0/',
    socials = '[
        {"platform":"Website","url":"https://kokonut.network"},
        {"platform":"Hub","url":"https://hub.kokonut.network/projects/41"}
    ]'::jsonb,
    relevant_to = '[
        {"grantPoolId":"daoip-5:Kokonut:grantPool:public-goods", "grantPoolName":"Kokonut Public Goods"},
        {"grantPoolId":"daoip-5:Kokonut:grantPool:regenerative-farms", "grantPoolName":"Regenerative Farm Replication"}
    ]'::jsonb,
    members_uri = 'https://hub.kokonut.network/projects/41/members.json',
    attestation_issuers_uri = 'https://hub.kokonut.network/projects/41/attestation-issuers.json',
    daoip5_extensions = '{
        "kokonut:commonDataSchema":"common-data-schema-v1",
        "kokonut:dataHub":"https://hub.kokonut.network/projects/41",
        "kokonut:farmSlug":"kokonut-adelphi",
        "kokonut:ebfBasicOnboarding":true
    }'::jsonb,
    founders = '[
        {
            "name": "Kokonut Collective",
            "role": "founding_team",
            "public_figure": true,
            "socials": [{"platform":"Website","url":"https://kokonut.network"}]
        }
    ]'::jsonb,
    updated_at = NOW()
WHERE id = 'a0000000-0000-0000-0000-000000000500';

UPDATE crop_cycle
SET expected_price_per_unit = CASE crop_id
        WHEN 'a0000000-0000-0000-0000-000000000030' THEN 700.00
        WHEN 'a0000000-0000-0000-0000-000000000031' THEN 1200.00
        WHEN 'a0000000-0000-0000-0000-000000000032' THEN 900.00
        WHEN 'a0000000-0000-0000-0000-000000000033' THEN 850.00
        WHEN 'a0000000-0000-0000-0000-000000000034' THEN 0.25
        ELSE expected_price_per_unit
    END,
    expected_revenue = ROUND((expected_yield * CASE crop_id
        WHEN 'a0000000-0000-0000-0000-000000000030' THEN 700.00
        WHEN 'a0000000-0000-0000-0000-000000000031' THEN 1200.00
        WHEN 'a0000000-0000-0000-0000-000000000032' THEN 900.00
        WHEN 'a0000000-0000-0000-0000-000000000033' THEN 850.00
        WHEN 'a0000000-0000-0000-0000-000000000034' THEN 0.25
        ELSE 0
    END)::numeric, 2),
    actual_revenue = ROUND((actual_yield * CASE crop_id
        WHEN 'a0000000-0000-0000-0000-000000000030' THEN 700.00
        WHEN 'a0000000-0000-0000-0000-000000000031' THEN 1200.00
        WHEN 'a0000000-0000-0000-0000-000000000032' THEN 900.00
        WHEN 'a0000000-0000-0000-0000-000000000033' THEN 850.00
        WHEN 'a0000000-0000-0000-0000-000000000034' THEN 0.25
        ELSE 0
    END)::numeric, 2),
    updated_at = NOW()
WHERE location_id = 'a0000000-0000-0000-0000-000000000001';

INSERT INTO tenure_rights_assessment (
    id, location_id, farm_id, property_id, farm_registry_record_id,
    assessment_date, assessor, tenure_type, rights_summary,
    community_effects_forecast, nearby_area_survey, risk_level,
    mitigation_plan, status, verified_at, schema_version,
    source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000690',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'a0000000-0000-0000-0000-000000000005',
    'a0000000-0000-0000-0000-000000000500',
    '2025-09-15',
    'Adelphi Farm Lead',
    'communal',
    'Adelphi is modeled as a community-first farm with documented managed-area boundaries and public-good allocation commitments.',
    'Forecast is positive when local hiring, bioinput training, transparent public summaries, and opt-in evidence collection are maintained.',
    '{
        "nearby_area":"Gonzalo / Sabana Grande de Boya",
        "survey_method":"operator interview and community context review",
        "community_effects": ["local food production", "bioinput skills transfer", "women-led farm operations"],
        "watch_items": ["privacy of household-level evidence", "clear benefit-sharing communication"]
    }'::jsonb,
    'low',
    'Maintain opt-in evidence collection, publish only aggregate/public metadata, and review benefit-sharing quarterly with farm operators.',
    'published',
    '2025-09-20 10:00:00+00',
    'farm-onboarding-v1',
    'pilot_seed',
    'tenure-rights-adelphi-2025-09',
    '{"record_type":"tenure_rights_assessment","source":"Adelphi onboarding review"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    assessment_date = EXCLUDED.assessment_date,
    assessor = EXCLUDED.assessor,
    tenure_type = EXCLUDED.tenure_type,
    rights_summary = EXCLUDED.rights_summary,
    community_effects_forecast = EXCLUDED.community_effects_forecast,
    nearby_area_survey = EXCLUDED.nearby_area_survey,
    risk_level = EXCLUDED.risk_level,
    mitigation_plan = EXCLUDED.mitigation_plan,
    status = EXCLUDED.status,
    verified_at = EXCLUDED.verified_at,
    schema_version = EXCLUDED.schema_version,
    source_system = EXCLUDED.source_system,
    source_id = EXCLUDED.source_id,
    source_raw = EXCLUDED.source_raw,
    updated_at = NOW();

INSERT INTO attestation_plan (
    id, location_id, attestation_type, target_date, status, estimated_cost_usd,
    estimated_value_usd, documentation_urls, notes, metadata
) VALUES (
    'a0000000-0000-0000-0000-000000000691',
    'a0000000-0000-0000-0000-000000000001',
    'carbon_credits',
    '2026-12-31',
    'planned',
    750.00,
    525.00,
    ARRAY['https://hub.kokonut.network/projects/41/carbon-plan'],
    'Pilot carbon credit planning estimate linked to soil carbon and forecast outputs.',
    '{"registry_candidates":["regen_registry_candidate","celo_eas"],"index_component":"planned_carbon_credit_value_usd"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    attestation_type = EXCLUDED.attestation_type,
    target_date = EXCLUDED.target_date,
    status = EXCLUDED.status,
    estimated_cost_usd = EXCLUDED.estimated_cost_usd,
    estimated_value_usd = EXCLUDED.estimated_value_usd,
    documentation_urls = EXCLUDED.documentation_urls,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
