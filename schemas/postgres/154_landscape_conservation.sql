-- ============================================================
-- 154_landscape_conservation.sql — Landscape Conservation & Connectivity
-- Habitat zones, wildlife corridors, hedgerows, buffer zone
-- monitoring, and landscape-level biodiversity assessment.
-- ============================================================

-- ============================================================
-- HABITAT ZONE — Managed habitat areas
-- ============================================================

CREATE TABLE IF NOT EXISTS habitat_zone (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_name           VARCHAR(200) NOT NULL,
    habitat_type        VARCHAR(100) NOT NULL,
    area_ha             NUMERIC(8,2),
    perimeter_m         NUMERIC(10,2),
    description         TEXT,
    biodiversity_value  VARCHAR(20),
    gps_boundary        GEOMETRY,
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE habitat_zone DROP CONSTRAINT IF EXISTS chk_habitat_zone_type;
ALTER TABLE habitat_zone ADD CONSTRAINT chk_habitat_zone_type CHECK (habitat_type IN (
    'wetland', 'riparian', 'forest_patch', 'grassland', 'hedgerow',
    'orchard', 'agroforestry', 'other'
));

ALTER TABLE habitat_zone DROP CONSTRAINT IF EXISTS chk_habitat_zone_biodiversity;
ALTER TABLE habitat_zone ADD CONSTRAINT chk_habitat_zone_biodiversity CHECK (biodiversity_value IN (
    'low', 'medium', 'high', 'critical'
));

ALTER TABLE habitat_zone DROP CONSTRAINT IF EXISTS chk_habitat_zone_status;
ALTER TABLE habitat_zone ADD CONSTRAINT chk_habitat_zone_status CHECK (status IN (
    'active', 'inactive', 'degraded', 'restored', 'archived'
));

CREATE INDEX IF NOT EXISTS idx_habitat_zone_location ON habitat_zone(location_id);
CREATE INDEX IF NOT EXISTS idx_habitat_zone_type ON habitat_zone(habitat_type);
CREATE INDEX IF NOT EXISTS idx_habitat_zone_biodiversity ON habitat_zone(biodiversity_value);
CREATE INDEX IF NOT EXISTS idx_habitat_zone_status ON habitat_zone(status);

-- ============================================================
-- WILDLIFE CORRIDOR — Connectivity corridors between habitats
-- ============================================================

CREATE TABLE IF NOT EXISTS wildlife_corridor (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    corridor_name       VARCHAR(200) NOT NULL,
    source_habitat_id   UUID REFERENCES habitat_zone(id) ON DELETE SET NULL,
    target_habitat_id   UUID REFERENCES habitat_zone(id) ON DELETE SET NULL,
    width_m             NUMERIC(8,2),
    length_m            NUMERIC(10,2),
    vegetation_type     VARCHAR(100),
    condition           VARCHAR(50),
    last_survey_date    DATE,
    notes               TEXT,
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE wildlife_corridor DROP CONSTRAINT IF EXISTS chk_corridor_condition;
ALTER TABLE wildlife_corridor ADD CONSTRAINT chk_corridor_condition CHECK (condition IN (
    'excellent', 'good', 'fair', 'poor', 'degraded'
));

ALTER TABLE wildlife_corridor DROP CONSTRAINT IF EXISTS chk_corridor_status;
ALTER TABLE wildlife_corridor ADD CONSTRAINT chk_corridor_status CHECK (status IN (
    'active', 'inactive', 'restored', 'degraded', 'archived'
));

CREATE INDEX IF NOT EXISTS idx_corridor_location ON wildlife_corridor(location_id);
CREATE INDEX IF NOT EXISTS idx_corridor_source ON wildlife_corridor(source_habitat_id);
CREATE INDEX IF NOT EXISTS idx_corridor_target ON wildlife_corridor(target_habitat_id);
CREATE INDEX IF NOT EXISTS idx_corridor_condition ON wildlife_corridor(condition);
CREATE INDEX IF NOT EXISTS idx_corridor_status ON wildlife_corridor(status);

-- ============================================================
-- HEDGEROW RECORD — Hedgerow and windbreak tracking
-- ============================================================

CREATE TABLE IF NOT EXISTS hedgerow_record (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    hedgerow_name       VARCHAR(200),
    species_mix         JSONB DEFAULT '[]',
    length_m            NUMERIC(10,2),
    height_m            NUMERIC(5,2),
    age_years           INTEGER,
    planting_date       DATE,
    last_maintenance    DATE,
    condition           VARCHAR(50),
    purpose             JSONB DEFAULT '[]',
    notes               TEXT,
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE hedgerow_record DROP CONSTRAINT IF EXISTS chk_hedgerow_condition;
ALTER TABLE hedgerow_record ADD CONSTRAINT chk_hedgerow_condition CHECK (condition IN (
    'excellent', 'good', 'fair', 'poor'
));

ALTER TABLE hedgerow_record DROP CONSTRAINT IF EXISTS chk_hedgerow_status;
ALTER TABLE hedgerow_record ADD CONSTRAINT chk_hedgerow_status CHECK (status IN (
    'active', 'inactive', 'maintained', 'needs_attention', 'removed'
));

CREATE INDEX IF NOT EXISTS idx_hedgerow_location ON hedgerow_record(location_id);
CREATE INDEX IF NOT EXISTS idx_hedgerow_condition ON hedgerow_record(condition);
CREATE INDEX IF NOT EXISTS idx_hedgerow_status ON hedgerow_record(status);
CREATE INDEX IF NOT EXISTS idx_hedgerow_species ON hedgerow_record USING GIN (species_mix);
CREATE INDEX IF NOT EXISTS idx_hedgerow_purpose ON hedgerow_record USING GIN (purpose);

-- ============================================================
-- BUFFER ZONE MONITORING — Buffer zone compliance checks
-- ============================================================

CREATE TABLE IF NOT EXISTS buffer_zone_monitoring (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id             UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    habitat_zone_id         UUID REFERENCES habitat_zone(id) ON DELETE SET NULL,
    check_date              DATE NOT NULL,
    buffer_width_m          NUMERIC(8,2),
    minimum_required_m      NUMERIC(8,2),
    compliant               BOOLEAN,
    vegetation_coverage_pct NUMERIC(5,2),
    erosion_observed        BOOLEAN DEFAULT FALSE,
    notes                   TEXT,
    status                  VARCHAR(50) NOT NULL DEFAULT 'recorded',
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE buffer_zone_monitoring DROP CONSTRAINT IF EXISTS chk_buffer_status;
ALTER TABLE buffer_zone_monitoring ADD CONSTRAINT chk_buffer_status CHECK (status IN (
    'recorded', 'verified', 'action_required', 'resolved'
));

CREATE INDEX IF NOT EXISTS idx_buffer_location ON buffer_zone_monitoring(location_id);
CREATE INDEX IF NOT EXISTS idx_buffer_habitat ON buffer_zone_monitoring(habitat_zone_id);
CREATE INDEX IF NOT EXISTS idx_buffer_check_date ON buffer_zone_monitoring(check_date DESC);
CREATE INDEX IF NOT EXISTS idx_buffer_compliant ON buffer_zone_monitoring(compliant);
CREATE INDEX IF NOT EXISTS idx_buffer_status ON buffer_zone_monitoring(status);

-- ============================================================
-- LANDSCAPE BIODIVERSITY SCORE — Landscape-level biodiversity assessment
-- ============================================================

CREATE TABLE IF NOT EXISTS landscape_biodiversity_score (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id             UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    assessment_date         DATE NOT NULL,
    species_richness        INTEGER,
    shannon_index           NUMERIC(5,3),
    habitat_diversity_index NUMERIC(5,3),
    connectivity_score      NUMERIC(5,2),
    overall_score           NUMERIC(5,2),
    assessor                VARCHAR(200),
    notes                   TEXT,
    status                  VARCHAR(50) NOT NULL DEFAULT 'recorded',
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE landscape_biodiversity_score DROP CONSTRAINT IF EXISTS chk_biodiversity_score_status;
ALTER TABLE landscape_biodiversity_score ADD CONSTRAINT chk_biodiversity_score_status CHECK (status IN (
    'recorded', 'verified', 'published'
));

CREATE INDEX IF NOT EXISTS idx_biodiversity_location ON landscape_biodiversity_score(location_id);
CREATE INDEX IF NOT EXISTS idx_biodiversity_date ON landscape_biodiversity_score(assessment_date DESC);
CREATE INDEX IF NOT EXISTS idx_biodiversity_status ON landscape_biodiversity_score(status);

-- ============================================================
-- VIEWS
-- ============================================================

-- Habitat zones with area and biodiversity value
CREATE OR REPLACE VIEW v_habitat_summary AS
SELECT
    hz.id AS habitat_id,
    hz.location_id,
    l.name AS location_name,
    hz.zone_name,
    hz.habitat_type,
    hz.area_ha,
    hz.perimeter_m,
    hz.biodiversity_value,
    hz.status,
    (SELECT COUNT(*) FROM wildlife_corridor wc
     WHERE wc.source_habitat_id = hz.id OR wc.target_habitat_id = hz.id
    ) AS corridor_count,
    (SELECT COUNT(*) FROM buffer_zone_monitoring bzm
     WHERE bzm.habitat_zone_id = hz.id AND bzm.compliant = TRUE
    ) AS compliant_buffer_checks,
    (SELECT COUNT(*) FROM buffer_zone_monitoring bzm
     WHERE bzm.habitat_zone_id = hz.id
    ) AS total_buffer_checks,
    hz.created_at,
    hz.updated_at
FROM habitat_zone hz
JOIN location l ON l.id = hz.location_id;

-- Corridors with condition and connectivity
CREATE OR REPLACE VIEW v_corridor_status AS
SELECT
    wc.id AS corridor_id,
    wc.location_id,
    l.name AS location_name,
    wc.corridor_name,
    src.zone_name AS source_habitat,
    tgt.zone_name AS target_habitat,
    wc.width_m,
    wc.length_m,
    wc.vegetation_type,
    wc.condition,
    wc.last_survey_date,
    wc.status,
    CASE
        WHEN wc.condition IN ('excellent', 'good') THEN 'connected'
        WHEN wc.condition = 'fair' THEN 'partially_connected'
        ELSE 'disconnected'
    END AS connectivity_status,
    wc.created_at,
    wc.updated_at
FROM wildlife_corridor wc
JOIN location l ON l.id = wc.location_id
LEFT JOIN habitat_zone src ON src.id = wc.source_habitat_id
LEFT JOIN habitat_zone tgt ON tgt.id = wc.target_habitat_id;

-- Buffer zone compliance rates
CREATE OR REPLACE VIEW v_buffer_compliance AS
SELECT
    bzm.location_id,
    l.name AS location_name,
    bzm.habitat_zone_id,
    hz.zone_name AS habitat_zone_name,
    COUNT(*) AS total_checks,
    COUNT(*) FILTER (WHERE bzm.compliant = TRUE) AS compliant_checks,
    ROUND(
        COUNT(*) FILTER (WHERE bzm.compliant = TRUE)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100, 1
    ) AS compliance_rate_pct,
    AVG(bzm.buffer_width_m) AS avg_buffer_width_m,
    AVG(bzm.minimum_required_m) AS avg_minimum_required_m,
    AVG(bzm.vegetation_coverage_pct) AS avg_vegetation_coverage_pct,
    COUNT(*) FILTER (WHERE bzm.erosion_observed = TRUE) AS erosion_incidents,
    MAX(bzm.check_date) AS last_check_date
FROM buffer_zone_monitoring bzm
JOIN location l ON l.id = bzm.location_id
LEFT JOIN habitat_zone hz ON hz.id = bzm.habitat_zone_id
GROUP BY bzm.location_id, l.name, bzm.habitat_zone_id, hz.zone_name;

-- Biodiversity scores over time
CREATE OR REPLACE VIEW v_landscape_biodiversity_trends AS
SELECT
    lbs.location_id,
    l.name AS location_name,
    lbs.assessment_date,
    lbs.species_richness,
    lbs.shannon_index,
    lbs.habitat_diversity_index,
    lbs.connectivity_score,
    lbs.overall_score,
    lbs.assessor,
    lbs.status,
    LAG(lbs.overall_score) OVER (
        PARTITION BY lbs.location_id ORDER BY lbs.assessment_date
    ) AS prev_overall_score,
    lbs.overall_score - LAG(lbs.overall_score) OVER (
        PARTITION BY lbs.location_id ORDER BY lbs.assessment_date
    ) AS score_change,
    LAG(lbs.species_richness) OVER (
        PARTITION BY lbs.location_id ORDER BY lbs.assessment_date
    ) AS prev_species_richness,
    LAG(lbs.connectivity_score) OVER (
        PARTITION BY lbs.location_id ORDER BY lbs.assessment_date
    ) AS prev_connectivity_score,
    lbs.created_at
FROM landscape_biodiversity_score lbs
JOIN location l ON l.id = lbs.location_id;

-- ============================================================
-- SEED DATA: Common habitat types and biodiversity values
-- for East African smallholder contexts
-- ============================================================

-- Habitat type reference data stored in metadata for reference;
-- seed values below populate sample zones for the Adelphi pilot.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM location WHERE id = 'a0000000-0000-0000-0000-000000000001') THEN
        INSERT INTO habitat_zone (location_id, zone_name, habitat_type, area_ha, perimeter_m, biodiversity_value, description, status) VALUES
        ('a0000000-0000-0000-0000-000000000001', 'Riparian Buffer', 'riparian', 0.50, 320, 'high', 'Natural riparian zone along seasonal stream providing erosion control and wildlife habitat', 'active'),
        ('a0000000-0000-0000-0000-000000000001', 'Agroforestry Block', 'agroforestry', 2.00, 560, 'medium', 'Mixed tree-crop system with indigenous and fruit trees integrated with annual crops', 'active'),
        ('a0000000-0000-0000-0000-000000000001', 'Wetland Margin', 'wetland', 0.30, 220, 'critical', 'Seasonal wetland fringe supporting amphibians, invertebrates, and water filtration', 'active'),
        ('a0000000-0000-0000-0000-000000000001', 'Forest Patch', 'forest_patch', 1.20, 440, 'high', 'Secondary indigenous forest remnant with canopy cover and understory diversity', 'active'),
        ('a0000000-0000-0000-0000-000000000001', 'Hedgerow Network', 'hedgerow', 0.15, 680, 'medium', 'Multi-species hedgerow system providing windbreak and pollinator corridor', 'active'),
        ('a0000000-0000-0000-0000-000000000001', 'Grassland Reserve', 'grassland', 0.80, 360, 'medium', 'Natural grassland maintained for soil conservation and grazing rotation', 'active')
        ON CONFLICT DO NOTHING;

        INSERT INTO hedgerow_record (location_id, hedgerow_name, species_mix, length_m, height_m, age_years, condition, purpose, status) VALUES
        ('a0000000-0000-0000-0000-000000000001', 'North Windbreak', '["calliandra", "leucaena", "grevillea"]', 180.00, 4.5, 5, 'good', '["windbreak", "biodiversity", "erosion_control"]', 'active'),
        ('a0000000-0000-0000-0000-000000000001', 'Stream Boundary Hedge', '["mukunyani", "kei_apple", "thorn_apple"]', 120.00, 3.0, 8, 'excellent', '["boundary", "biodiversity", "erosion_control"]', 'active'),
        ('a0000000-0000-0000-0000-000000000001', 'Field Margin Strip', '["sweet_bay", "silver_leaved_desmodium", "glyricidia"]', 95.00, 2.5, 3, 'fair', '["biodiversity", "erosion_control"]', 'active')
        ON CONFLICT DO NOTHING;

        INSERT INTO buffer_zone_monitoring (location_id, habitat_zone_id, check_date, buffer_width_m, minimum_required_m, compliant, vegetation_coverage_pct, erosion_observed, status) VALUES
        ('a0000000-0000-0000-0000-000000000001',
         (SELECT id FROM habitat_zone WHERE zone_name = 'Riparian Buffer' AND location_id = 'a0000000-0000-0000-0000-000000000001' LIMIT 1),
         CURRENT_DATE - 30, 12.00, 10.00, TRUE, 85.50, FALSE, 'verified'),
        ('a0000000-0000-0000-0000-000000000001',
         (SELECT id FROM habitat_zone WHERE zone_name = 'Wetland Margin' AND location_id = 'a0000000-0000-0000-0000-000000000001' LIMIT 1),
         CURRENT_DATE - 15, 8.50, 15.00, FALSE, 60.00, TRUE, 'action_required')
        ON CONFLICT DO NOTHING;

        INSERT INTO landscape_biodiversity_score (location_id, assessment_date, species_richness, shannon_index, habitat_diversity_index, connectivity_score, overall_score, assessor, status) VALUES
        ('a0000000-0000-0000-0000-000000000001', CURRENT_DATE - 90, 34, 2.450, 1.800, 6.50, 7.20, 'Field Survey Team', 'verified'),
        ('a0000000-0000-0000-0000-000000000001', CURRENT_DATE - 30, 38, 2.620, 1.950, 7.00, 7.80, 'Field Survey Team', 'recorded')
        ON CONFLICT DO NOTHING;
    END IF;
END $$;
