-- ============================================================
-- 027_farm_onboarding_profile.sql — Farm onboarding and Data Hub profile
-- ============================================================

-- Farm identity and EBF basic onboarding fields. Keep project/publication
-- metadata on farm_registry_record; farm remains the farm profile source.
ALTER TABLE farm ADD COLUMN IF NOT EXISTS logo_url TEXT;
ALTER TABLE farm ADD COLUMN IF NOT EXISTS logo_file_id UUID REFERENCES file_upload(id) ON DELETE SET NULL;
ALTER TABLE farm ADD COLUMN IF NOT EXISTS traditional_name TEXT;
ALTER TABLE farm ADD COLUMN IF NOT EXISTS languages TEXT[] DEFAULT '{}';
ALTER TABLE farm ADD COLUMN IF NOT EXISTS global_standard_certifications TEXT[] DEFAULT '{}';
ALTER TABLE farm ADD COLUMN IF NOT EXISTS economic_sectors TEXT[] DEFAULT '{}';
ALTER TABLE farm ADD COLUMN IF NOT EXISTS credits_registries TEXT[] DEFAULT '{}';
ALTER TABLE farm ADD COLUMN IF NOT EXISTS data_privacy_status VARCHAR(50) DEFAULT 'internal_review';
ALTER TABLE farm ADD COLUMN IF NOT EXISTS data_privacy_standard VARCHAR(100);
ALTER TABLE farm ADD COLUMN IF NOT EXISTS data_privacy_criteria JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_farm_languages ON farm USING GIN(languages);
CREATE INDEX IF NOT EXISTS idx_farm_certifications ON farm USING GIN(global_standard_certifications);
CREATE INDEX IF NOT EXISTS idx_farm_economic_sectors ON farm USING GIN(economic_sectors);
CREATE INDEX IF NOT EXISTS idx_farm_credits_registries ON farm USING GIN(credits_registries);
CREATE INDEX IF NOT EXISTS idx_farm_data_privacy_status ON farm(data_privacy_status);

-- DAOIP-5 project/profile fields for farm registry records. DAOIP-5 app/grant
-- applications can be derived from these and existing funding/governance rows.
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS daoip5_project_id TEXT;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS projects_uri TEXT;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS content_uri TEXT;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS cover_image_url TEXT;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS license_uri TEXT;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS socials JSONB DEFAULT '[]';
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS relevant_to JSONB DEFAULT '[]';
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS members_uri TEXT;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS attestation_issuers_uri TEXT;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS daoip5_extensions JSONB DEFAULT '{}';
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS founders JSONB DEFAULT '[]';

CREATE INDEX IF NOT EXISTS idx_farm_registry_daoip5_project ON farm_registry_record(daoip5_project_id);
CREATE INDEX IF NOT EXISTS idx_farm_registry_founders ON farm_registry_record USING GIN(founders);

CREATE TABLE IF NOT EXISTS tenure_rights_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    property_id UUID REFERENCES property(id) ON DELETE SET NULL,
    farm_registry_record_id UUID REFERENCES farm_registry_record(id) ON DELETE SET NULL,
    assessment_date DATE NOT NULL,
    assessor VARCHAR(255),
    tenure_type VARCHAR(100), -- titled, leased, communal, customary, informal, mixed, unknown
    rights_summary TEXT,
    community_effects_forecast TEXT,
    nearby_area_survey JSONB DEFAULT '{}',
    risk_level VARCHAR(50), -- low, medium, high, critical
    mitigation_plan TEXT,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'farm-onboarding-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE tenure_rights_assessment ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_tenure_rights_location ON tenure_rights_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_tenure_rights_farm ON tenure_rights_assessment(farm_id);
CREATE INDEX IF NOT EXISTS idx_tenure_rights_property ON tenure_rights_assessment(property_id);
CREATE INDEX IF NOT EXISTS idx_tenure_rights_registry ON tenure_rights_assessment(farm_registry_record_id);
CREATE INDEX IF NOT EXISTS idx_tenure_rights_status ON tenure_rights_assessment(status);

-- Species in Kokonut/Baserow maps to crop. This view exposes the requested
-- annual forecasted revenue per forecasted harvest per plot without storing a
-- stale editable aggregate on crop.
CREATE OR REPLACE VIEW v_crop_forecast_summary AS
WITH latest_cycle_forecasts AS (
    SELECT DISTINCT ON (fo.crop_cycle_id, fo.metric_name)
        fo.crop_cycle_id,
        fo.metric_name,
        fo.value,
        fo.period_start,
        fo.period_end,
        fo.calculated_at
    FROM forecast_output fo
    WHERE fo.crop_cycle_id IS NOT NULL
      AND fo.metric_name IN ('crop_projected_revenue_usd', 'crop_survival_rate_pct')
    ORDER BY fo.crop_cycle_id, fo.metric_name, fo.calculated_at DESC
), crop_rollup AS (
    SELECT
        c.id AS crop_id,
        c.name AS species_name,
        c.scientific_name,
        c.crop_category,
        cc.location_id,
        COUNT(DISTINCT p.id) AS forecasted_plot_count,
        COUNT(DISTINCT cc.id) FILTER (WHERE cc.expected_harvest_date IS NOT NULL OR cc.actual_harvest_date IS NOT NULL) AS forecasted_harvest_count,
        SUM(COALESCE(rev.value, cc.expected_revenue, cc.actual_revenue, 0)) AS total_annual_forecasted_revenue_usd,
        AVG(survival.value) AS crop_survival_rate_pct,
        MAX(GREATEST(COALESCE(rev.calculated_at, 'epoch'::timestamptz), COALESCE(survival.calculated_at, 'epoch'::timestamptz))) AS latest_forecasted_at
    FROM crop c
    JOIN crop_cycle cc ON cc.crop_id = c.id
    JOIN plot p ON p.id = cc.plot_id
    LEFT JOIN latest_cycle_forecasts rev ON rev.crop_cycle_id = cc.id AND rev.metric_name = 'crop_projected_revenue_usd'
    LEFT JOIN latest_cycle_forecasts survival ON survival.crop_cycle_id = cc.id AND survival.metric_name = 'crop_survival_rate_pct'
    GROUP BY c.id, c.name, c.scientific_name, c.crop_category, cc.location_id
)
SELECT
    crop_id,
    species_name,
    scientific_name,
    crop_category,
    location_id,
    forecasted_plot_count,
    forecasted_harvest_count,
    total_annual_forecasted_revenue_usd,
    CASE
        WHEN forecasted_plot_count > 0 AND forecasted_harvest_count > 0
        THEN ROUND((total_annual_forecasted_revenue_usd / forecasted_plot_count / forecasted_harvest_count)::numeric, 4)
        ELSE NULL
    END AS annual_forecasted_revenue_per_harvest_per_plot_usd,
    crop_survival_rate_pct,
    NULLIF(latest_forecasted_at, 'epoch'::timestamptz) AS latest_forecasted_at
FROM crop_rollup;

CREATE OR REPLACE VIEW v_public_farm_places AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    f.id AS farm_id,
    f.name AS farm_name,
    f.traditional_name,
    f.logo_url,
    p.id AS plot_id,
    p.name AS plot_name,
    fz.id AS zone_id,
    fz.name AS zone_name,
    fz.zone_type,
    COALESCE(fz.area_m2, CASE WHEN p.area_unit = 'hectares' THEN p.area * 10000 ELSE p.area END) AS area_m2,
    COUNT(DISTINCT so.id) AS flora_fauna_observation_count,
    COUNT(DISTINCT so.species_name) AS distinct_flora_fauna_count
FROM location l
JOIN farm f ON f.location_id = l.id
LEFT JOIN plot p ON p.farm_id = f.id
LEFT JOIN farm_zone fz ON fz.plot_id = p.id OR (fz.plot_id IS NULL AND fz.location_id = l.id)
LEFT JOIN species_observation so ON so.plot_id = p.id OR (so.plot_id IS NULL AND so.location_id = l.id)
WHERE l.status = 'active'
  AND f.status = 'active'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id
        AND fr.status IN ('verified', 'published')
  )
GROUP BY l.id, l.name, f.id, f.name, f.traditional_name, f.logo_url, p.id, p.name, fz.id, fz.name, fz.zone_type, fz.area_m2, p.area, p.area_unit;

CREATE OR REPLACE VIEW v_public_flora_fauna_summary AS
SELECT
    so.location_id,
    l.name AS location_name,
    f.id AS farm_id,
    f.name AS farm_name,
    p.id AS plot_id,
    p.name AS plot_name,
    so.species_category,
    so.species_name,
    so.species_common_name,
    COUNT(*) AS observation_count,
    SUM(COALESCE(so.count, 0)) AS total_count,
    MIN(so.observation_date) AS first_observed_at,
    MAX(so.observation_date) AS latest_observed_at
FROM species_observation so
JOIN location l ON l.id = so.location_id
LEFT JOIN plot p ON p.id = so.plot_id
LEFT JOIN farm f ON f.id = p.farm_id
WHERE l.status = 'active'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id
        AND fr.status IN ('verified', 'published')
  )
GROUP BY so.location_id, l.name, f.id, f.name, p.id, p.name, so.species_category, so.species_name, so.species_common_name;

CREATE OR REPLACE VIEW v_public_project_carbon_credit_index AS
SELECT
    fr.id AS farm_registry_record_id,
    fr.location_id,
    l.name AS location_name,
    COALESCE(SUM(DISTINCT fo.value) FILTER (WHERE fo.metric_name = 'carbon_credit_value_usd'), 0) AS forecasted_carbon_credit_value_usd,
    COALESCE(SUM(DISTINCT ap.estimated_value_usd) FILTER (WHERE ap.attestation_type = 'carbon_credits'), 0) AS planned_carbon_credit_value_usd,
    COALESCE(SUM(DISTINCT re.amount_usd) FILTER (WHERE re.revenue_type = 'carbon_credit' AND re.status IN ('verified', 'published')), 0) AS realized_carbon_credit_value_usd,
    COALESCE(SUM(DISTINCT fo.value) FILTER (WHERE fo.metric_name = 'carbon_credit_value_usd'), 0)
      + COALESCE(SUM(DISTINCT ap.estimated_value_usd) FILTER (WHERE ap.attestation_type = 'carbon_credits'), 0)
      + COALESCE(SUM(DISTINCT re.amount_usd) FILTER (WHERE re.revenue_type = 'carbon_credit' AND re.status IN ('verified', 'published')), 0)
      AS carbon_credits_index_usd
FROM farm_registry_record fr
JOIN location l ON l.id = fr.location_id
LEFT JOIN forecast_output fo ON fo.location_id = fr.location_id
LEFT JOIN attestation_plan ap ON ap.location_id = fr.location_id
LEFT JOIN revenue_event re ON re.location_id = fr.location_id
WHERE fr.status IN ('verified', 'published')
  AND l.status = 'active'
GROUP BY fr.id, fr.location_id, l.name;

CREATE OR REPLACE VIEW v_daoip5_project_json AS
SELECT
    fr.id AS farm_registry_record_id,
    jsonb_build_object(
        '@context', 'http://www.daostar.org/schemas',
        'name', l.name,
        'type', 'DAO',
        'projects', jsonb_build_array(jsonb_build_object(
            'type', 'Project',
            'id', COALESCE(fr.daoip5_project_id, 'daoip-5:Kokonut:project:' || fr.registry_slug),
            'name', l.name,
            'description', fr.project_summary,
            'contentURI', fr.content_uri,
            'membersURI', fr.members_uri,
            'attestationIssuersURI', fr.attestation_issuers_uri,
            'relevantTo', fr.relevant_to,
            'image', COALESCE(fr.image_url, f.logo_url),
            'coverImage', fr.cover_image_url,
            'licenseURI', fr.license_uri,
            'socials', fr.socials,
            'founders', COALESCE(fr.founders, '[]'::jsonb),
            'extensions', COALESCE(fr.daoip5_extensions, '{}'::jsonb) || jsonb_build_object(
                'kokonut:farmRegistryRecordId', fr.id,
                'kokonut:locationId', fr.location_id,
                'kokonut:dataPrivacyStatus', f.data_privacy_status,
                'kokonut:creditsRegistries', f.credits_registries,
                'kokonut:globalStandardCertifications', f.global_standard_certifications
            )
        ))
    ) AS project_json
FROM farm_registry_record fr
JOIN location l ON l.id = fr.location_id
LEFT JOIN farm f ON f.id = fr.farm_id
WHERE fr.status IN ('verified', 'published');

INSERT INTO schema_version (version, description, applied_by)
VALUES ('farm-onboarding-v1', 'Farm onboarding profile, EBF fields, DAOIP-5 project metadata, and Data Hub views', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
