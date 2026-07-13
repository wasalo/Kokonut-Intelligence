-- 155_pollinator_health.sql
-- Pollinator Health: observation records, habitat mapping,
-- pesticide impact tracking, and managed hive monitoring.

BEGIN;

-- ============================================================
-- POLLINATOR OBSERVATION — Population monitoring records
-- ============================================================

CREATE TABLE IF NOT EXISTS pollinator_observation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id             UUID,
    observation_date    DATE NOT NULL,
    pollinator_type     VARCHAR(100) NOT NULL
        CHECK (pollinator_type IN (
            'honeybee', 'wild_bee', 'butterfly', 'moth',
            'beetle', 'fly', 'bird', 'bat', 'other'
        )),
    species_name        VARCHAR(200),
    count               INTEGER,
    observation_method  VARCHAR(100)
        CHECK (observation_method IN (
            'transect', 'pan_trap', 'visual_count', 'hive_weight', 'other'
        )),
    duration_minutes    INTEGER,
    flower_species      VARCHAR(200),
    weather_conditions  JSONB DEFAULT '{}',
    notes               TEXT,
    status              VARCHAR(50) DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'verified', 'reviewed', 'dismissed')),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pollinator_obs_location
    ON pollinator_observation (location_id, observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_pollinator_obs_plot
    ON pollinator_observation (plot_id, observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_pollinator_obs_type
    ON pollinator_observation (pollinator_type, observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_pollinator_obs_date
    ON pollinator_observation (observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_pollinator_obs_method
    ON pollinator_observation (observation_method, observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_pollinator_obs_status
    ON pollinator_observation (status, observation_date DESC);

-- ============================================================
-- POLLINATOR HABITAT — Pollinator-friendly habitat areas
-- ============================================================

CREATE TABLE IF NOT EXISTS pollinator_habitat (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    habitat_name        VARCHAR(200) NOT NULL,
    habitat_type        VARCHAR(100) NOT NULL
        CHECK (habitat_type IN (
            'wildflower_strip', 'hedgerow', 'nesting_site',
            'water_source', 'cover_crop', 'native_planting', 'other'
        )),
    area_m2             NUMERIC(10,2),
    plant_species       JSONB DEFAULT '[]',
    bloom_period        VARCHAR(100),
    nesting_features    JSONB DEFAULT '{}',
    condition           VARCHAR(50)
        CHECK (condition IN ('excellent', 'good', 'fair', 'poor')),
    last_maintenance    DATE,
    notes               TEXT,
    status              VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'degraded', 'removed')),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pollinator_habitat_location
    ON pollinator_habitat (location_id, status);
CREATE INDEX IF NOT EXISTS idx_pollinator_habitat_type
    ON pollinator_habitat (habitat_type, status);
CREATE INDEX IF NOT EXISTS idx_pollinator_habitat_condition
    ON pollinator_habitat (condition, location_id);

-- ============================================================
-- PESTICIDE IMPACT LOG — Pesticide impact on pollinators
-- ============================================================

CREATE TABLE IF NOT EXISTS pesticide_impact_log (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id                 UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    application_date            DATE NOT NULL,
    product_name                VARCHAR(200),
    active_ingredient           VARCHAR(200),
    toxicity_class              VARCHAR(50)
        CHECK (toxicity_class IN ('low', 'moderate', 'high', 'very_high')),
    pollinator_safe_period_days INTEGER,
    bloom_stage_at_application  VARCHAR(100),
    pollinator_mortality_observed BOOLEAN DEFAULT FALSE,
    mortality_pct               NUMERIC(5,2),
    notes                       TEXT,
    status                      VARCHAR(50) DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'verified', 'reviewed', 'dismissed')),
    metadata                    JSONB DEFAULT '{}',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pesticide_impact_location
    ON pesticide_impact_log (location_id, application_date DESC);
CREATE INDEX IF NOT EXISTS idx_pesticide_impact_date
    ON pesticide_impact_log (application_date DESC);
CREATE INDEX IF NOT EXISTS idx_pesticide_impact_toxicity
    ON pesticide_impact_log (toxicity_class, application_date DESC);
CREATE INDEX IF NOT EXISTS idx_pesticide_impact_mortality
    ON pesticide_impact_log (pollinator_mortality_observed, application_date DESC)
    WHERE pollinator_mortality_observed = TRUE;
CREATE INDEX IF NOT EXISTS idx_pesticide_impact_status
    ON pesticide_impact_log (status, application_date DESC);

-- ============================================================
-- HIVE RECORD — Managed honeybee hives
-- ============================================================

CREATE TABLE IF NOT EXISTS hive_record (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    hive_id             VARCHAR(100) NOT NULL,
    colony_strength     VARCHAR(50)
        CHECK (colony_strength IN ('strong', 'moderate', 'weak', 'dead')),
    queen_status        VARCHAR(50)
        CHECK (queen_status IN ('present', 'absent', 'replaced', 'unknown')),
    honey_yield_kg      NUMERIC(8,2),
    inspection_date     DATE,
    varroa_count        INTEGER,
    notes               TEXT,
    status              VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'decommissioned')),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hive_record_location
    ON hive_record (location_id, status);
CREATE INDEX IF NOT EXISTS idx_hive_record_hive_id
    ON hive_record (hive_id, location_id);
CREATE INDEX IF NOT EXISTS idx_hive_record_strength
    ON hive_record (colony_strength, location_id);
CREATE INDEX IF NOT EXISTS idx_hive_record_inspection
    ON hive_record (inspection_date DESC)
    WHERE inspection_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_hive_record_status
    ON hive_record (status, location_id);

-- ============================================================
-- VIEWS
-- ============================================================

-- Pollinator counts by type and trend over time
CREATE OR REPLACE VIEW v_pollinator_summary AS
SELECT
    po.location_id,
    l.name AS location_name,
    po.pollinator_type,
    po.observation_method,
    DATE_TRUNC('month', po.observation_date) AS observation_month,
    COUNT(*) AS observation_count,
    SUM(po.count) AS total_count,
    AVG(po.count) AS avg_count,
    MAX(po.count) AS max_count,
    MIN(po.observation_date) AS first_observed,
    MAX(po.observation_date) AS last_observed,
    COUNT(DISTINCT po.species_name) AS species_diversity
FROM pollinator_observation po
JOIN location l ON l.id = po.location_id
WHERE po.status != 'dismissed'
GROUP BY po.location_id, l.name, po.pollinator_type, po.observation_method,
         DATE_TRUNC('month', po.observation_date);

-- Habitat areas and conditions per location
CREATE OR REPLACE VIEW v_pollinator_habitat_inventory AS
SELECT
    ph.location_id,
    l.name AS location_name,
    ph.habitat_type,
    COUNT(*) AS habitat_count,
    SUM(ph.area_m2) AS total_area_m2,
    AVG(ph.area_m2) AS avg_area_m2,
    ph.condition,
    COUNT(*) FILTER (WHERE ph.condition = 'excellent') AS excellent_count,
    COUNT(*) FILTER (WHERE ph.condition = 'good') AS good_count,
    COUNT(*) FILTER (WHERE ph.condition = 'fair') AS fair_count,
    COUNT(*) FILTER (WHERE ph.condition = 'poor') AS poor_count,
    MAX(ph.last_maintenance) AS latest_maintenance,
    MIN(ph.bloom_period) AS earliest_bloom,
    MAX(ph.bloom_period) AS latest_bloom
FROM pollinator_habitat ph
JOIN location l ON l.id = ph.location_id
WHERE ph.status = 'active'
GROUP BY ph.location_id, l.name, ph.habitat_type, ph.condition;

-- Recent pesticide applications with pollinator risk rating
CREATE OR REPLACE VIEW v_pesticide_risk AS
SELECT
    pil.location_id,
    l.name AS location_name,
    pil.application_date,
    pil.product_name,
    pil.active_ingredient,
    pil.toxicity_class,
    CASE
        WHEN pil.toxicity_class = 'very_high' THEN 'critical'
        WHEN pil.toxicity_class = 'high' THEN 'high'
        WHEN pil.toxicity_class = 'moderate' THEN 'moderate'
        ELSE 'low'
    END AS risk_rating,
    pil.pollinator_safe_period_days,
    pil.bloom_stage_at_application,
    pil.pollinator_mortality_observed,
    pil.mortality_pct,
    pil.status
FROM pesticide_impact_log pil
JOIN location l ON l.id = pil.location_id
WHERE pil.application_date >= (CURRENT_DATE - INTERVAL '90 days')
ORDER BY pil.application_date DESC;

-- Hive health and productivity
CREATE OR REPLACE VIEW v_hive_status AS
SELECT
    hr.location_id,
    l.name AS location_name,
    hr.hive_id,
    hr.colony_strength,
    hr.queen_status,
    hr.honey_yield_kg,
    hr.inspection_date,
    hr.varroa_count,
    CASE
        WHEN hr.colony_strength = 'dead' THEN 'dead'
        WHEN hr.varroa_count > 100 THEN 'high_varroa'
        WHEN hr.queen_status = 'absent' THEN 'queenless'
        WHEN hr.colony_strength = 'weak' THEN 'weak'
        ELSE 'healthy'
    END AS health_status,
    hr.status
FROM hive_record hr
JOIN location l ON l.id = hr.location_id
WHERE hr.status = 'active';

-- ============================================================
-- SEED DATA: Common pollinator types and conservation
-- status in East Africa
-- ============================================================

-- Reference table for pollinator species conservation context
CREATE TABLE IF NOT EXISTS pollinator_species_reference (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pollinator_type     VARCHAR(100) NOT NULL,
    species_name        VARCHAR(200) NOT NULL,
    region              VARCHAR(100) DEFAULT 'East Africa',
    conservation_status VARCHAR(50)
        CHECK (conservation_status IN (
            'least_concern', 'near_threatened', 'vulnerable',
            'endangered', 'data_deficient', 'not_evaluated'
        )),
    ecological_role     TEXT,
    threat_notes        TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO pollinator_species_reference
    (pollinator_type, species_name, region, conservation_status, ecological_role, threat_notes)
VALUES
    ('honeybee', 'Apis mellifera scutellata', 'East Africa',
     'least_concern', 'Primary managed pollinator; honey production and crop pollination',
     'Varroa destructor, habitat loss, pesticide exposure, climate variability'),
    ('wild_bee', 'Xylocopa spp. (Carpenter bees)', 'East Africa',
     'least_concern', 'Buzz pollination for solanaceous crops; nest in dead wood',
     'Habitat loss, dead wood removal, insecticide exposure'),
    ('wild_bee', 'Megachile spp. (Leafcutter bees)', 'East Africa',
     'data_deficient', 'Nesting in cavities; important for legume and alfalfa pollination',
     'Nesting site availability, pesticide exposure'),
    ('wild_bee', 'Anthophora spp. (Digger bees)', 'East Africa',
     'data_deficient', 'Ground-nesting pollinators; early-season forage',
     'Soil disturbance, tillage practices'),
    ('butterfly', 'Danaus chrysippus (African Monarch)', 'East Africa',
     'least_concern', 'Long-distance pollinator; indicator species for ecosystem health',
     'Habitat fragmentation, pesticide drift, climate change'),
    ('butterfly', 'Papilio demodocus (Citrus swallowtail)', 'East Africa',
     'least_concern', 'Pollinator of citrus and wild umbellifers',
     'Pesticide use in citrus orchards, habitat loss'),
    ('moth', 'Agrius convolvuli (Hawk moth)', 'East Africa',
     'least_concern', 'Nocturnal pollinator of deep-tubed flowers',
     'Light pollution, habitat loss'),
    ('beetle', 'Scarabaeidae (Scarab beetles)', 'East Africa',
     'least_concern', 'Pollinator of palm, cycad, and protea species',
     'Pesticide exposure, habitat degradation'),
    ('fly', 'Syrphidae (Hoverflies)', 'East Africa',
     'data_deficient', 'Secondary pollinator; larvae are aphid predators',
     'Insecticide use, habitat loss of larval food sources'),
    ('bird', 'Nectarinia spp. (Sunbirds)', 'East Africa',
     'least_concern', 'Pollinator of Protea, aloes, and other bird-pollinated flora',
     'Habitat loss, invasive plant competition'),
    ('bat', 'Eidolon helvum (Straw-colored fruit bat)', 'East Africa',
     'near_threatened', 'Nocturnal pollinator and seed disperser for baobab and sausage tree',
     'Hunting, habitat loss, roost disturbance'),
    ('other', 'Locusts and grasshoppers (Orthoptera)', 'East Africa',
     'not_evaluated', 'Incidental pollinators; primarily herbivorous',
     'Pesticide use, habitat conversion')
ON CONFLICT DO NOTHING;

COMMIT;
