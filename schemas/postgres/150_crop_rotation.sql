-- ============================================================
-- 150_crop_rotation.sql — Crop Rotation Planning & Impact Tracking
-- Multi-season rotation plans, crop family reference, impact
-- records, and system-generated rotation recommendations.
-- ============================================================

-- ============================================================
-- CROP FAMILY REFERENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS crop_family (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_name     VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    example_crops   JSONB DEFAULT '[]',
    notes           TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- ROTATION PLAN
-- ============================================================

CREATE TABLE IF NOT EXISTS rotation_plan (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plan_name       VARCHAR(200) NOT NULL,
    plot_id         UUID,
    zone_id         UUID,
    duration_seasons INTEGER NOT NULL DEFAULT 4,
    start_season    VARCHAR(100),
    status          VARCHAR(50) NOT NULL DEFAULT 'draft',
    notes           TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE rotation_plan DROP CONSTRAINT IF EXISTS chk_rotation_plan_status;
ALTER TABLE rotation_plan ADD CONSTRAINT chk_rotation_plan_status CHECK (status IN (
    'draft', 'active', 'completed', 'archived'
));

CREATE INDEX IF NOT EXISTS idx_rotation_plan_location ON rotation_plan(location_id);
CREATE INDEX IF NOT EXISTS idx_rotation_plan_status ON rotation_plan(status);
CREATE INDEX IF NOT EXISTS idx_rotation_plan_plot ON rotation_plan(plot_id);
CREATE INDEX IF NOT EXISTS idx_rotation_plan_zone ON rotation_plan(zone_id);

-- ============================================================
-- ROTATION SLOT — individual seasons in a plan
-- ============================================================

CREATE TABLE IF NOT EXISTS rotation_slot (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id         UUID NOT NULL REFERENCES rotation_plan(id) ON DELETE CASCADE,
    season_number   INTEGER NOT NULL,
    season_name     VARCHAR(100),
    crop_name       VARCHAR(100) NOT NULL,
    crop_family_id  UUID REFERENCES crop_family(id),
    purpose         VARCHAR(100),
    expected_area_ha NUMERIC(8,2),
    notes           TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(plan_id, season_number)
);

ALTER TABLE rotation_slot DROP CONSTRAINT IF EXISTS chk_rotation_slot_purpose;
ALTER TABLE rotation_slot ADD CONSTRAINT chk_rotation_slot_purpose CHECK (purpose IN (
    'cash_crop', 'cover_crop', 'nitrogen_fixer', 'green_manure', 'break_crop'
));

CREATE INDEX IF NOT EXISTS idx_rotation_slot_plan ON rotation_slot(plan_id);
CREATE INDEX IF NOT EXISTS idx_rotation_slot_family ON rotation_slot(crop_family_id);
CREATE INDEX IF NOT EXISTS idx_rotation_slot_crop ON rotation_slot(crop_name);
CREATE INDEX IF NOT EXISTS idx_rotation_slot_purpose ON rotation_slot(purpose);

-- ============================================================
-- ROTATION IMPACT RECORD
-- ============================================================

CREATE TABLE IF NOT EXISTS rotation_impact_record (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id         UUID REFERENCES rotation_plan(id) ON DELETE SET NULL,
    slot_id         UUID REFERENCES rotation_slot(id) ON DELETE SET NULL,
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    record_date     DATE NOT NULL,
    impact_type     VARCHAR(100) NOT NULL,
    impact_direction VARCHAR(20) NOT NULL,
    severity_pct    NUMERIC(5,2),
    measurement_value NUMERIC(10,2),
    measurement_unit VARCHAR(50),
    notes           TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'recorded',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE rotation_impact_record DROP CONSTRAINT IF EXISTS chk_rotation_impact_type;
ALTER TABLE rotation_impact_record ADD CONSTRAINT chk_rotation_impact_type CHECK (impact_type IN (
    'disease_pressure', 'pest_pressure', 'soil_health',
    'yield_effect', 'weed_pressure'
));

ALTER TABLE rotation_impact_record DROP CONSTRAINT IF EXISTS chk_rotation_impact_direction;
ALTER TABLE rotation_impact_record ADD CONSTRAINT chk_rotation_impact_direction CHECK (impact_direction IN (
    'positive', 'neutral', 'negative'
));

ALTER TABLE rotation_impact_record DROP CONSTRAINT IF EXISTS chk_rotation_impact_status;
ALTER TABLE rotation_impact_record ADD CONSTRAINT chk_rotation_impact_status CHECK (status IN (
    'recorded', 'verified', 'dismissed'
));

CREATE INDEX IF NOT EXISTS idx_rotation_impact_plan ON rotation_impact_record(plan_id);
CREATE INDEX IF NOT EXISTS idx_rotation_impact_slot ON rotation_impact_record(slot_id);
CREATE INDEX IF NOT EXISTS idx_rotation_impact_location ON rotation_impact_record(location_id);
CREATE INDEX IF NOT EXISTS idx_rotation_impact_type ON rotation_impact_record(impact_type);
CREATE INDEX IF NOT EXISTS idx_rotation_impact_date ON rotation_impact_record(record_date DESC);
CREATE INDEX IF NOT EXISTS idx_rotation_impact_status ON rotation_impact_record(status);

-- ============================================================
-- ROTATION RECOMMENDATION
-- ============================================================

CREATE TABLE IF NOT EXISTS rotation_recommendation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id             UUID,
    recommended_crop    VARCHAR(100) NOT NULL,
    recommended_family_id UUID REFERENCES crop_family(id),
    reason              TEXT,
    soil_benefit        TEXT,
    pest_break_benefit  TEXT,
    confidence_score    NUMERIC(3,2),
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE rotation_recommendation DROP CONSTRAINT IF EXISTS chk_rotation_rec_status;
ALTER TABLE rotation_recommendation ADD CONSTRAINT chk_rotation_rec_status CHECK (status IN (
    'pending', 'accepted', 'rejected', 'implemented'
));

CREATE INDEX IF NOT EXISTS idx_rotation_rec_location ON rotation_recommendation(location_id);
CREATE INDEX IF NOT EXISTS idx_rotation_rec_plot ON rotation_recommendation(plot_id);
CREATE INDEX IF NOT EXISTS idx_rotation_rec_family ON rotation_recommendation(recommended_family_id);
CREATE INDEX IF NOT EXISTS idx_rotation_rec_status ON rotation_recommendation(status);
CREATE INDEX IF NOT EXISTS idx_rotation_rec_crop ON rotation_recommendation(recommended_crop);

-- ============================================================
-- VIEWS
-- ============================================================

-- Rotation plan summary with crop sequence and completion status
CREATE OR REPLACE VIEW v_rotation_plan_summary AS
SELECT
    rp.id AS plan_id,
    rp.plan_name,
    rp.location_id,
    l.name AS location_name,
    rp.plot_id,
    rp.zone_id,
    rp.duration_seasons,
    rp.start_season,
    rp.status,
    (SELECT COUNT(*) FROM rotation_slot rs WHERE rs.plan_id = rp.id) AS slot_count,
    ARRAY_AGG(
        rs.crop_name ORDER BY rs.season_number
    ) AS crop_sequence,
    ARRAY_AGG(
        cf.family_name ORDER BY rs.season_number
    ) AS family_sequence,
    (SELECT COUNT(*) FROM rotation_impact_record rip WHERE rip.plan_id = rp.id) AS impact_record_count,
    (SELECT COUNT(*) FROM rotation_impact_record rip
     WHERE rip.plan_id = rp.id AND rip.impact_direction = 'positive') AS positive_impact_count,
    (SELECT COUNT(*) FROM rotation_impact_record rip
     WHERE rip.plan_id = rp.id AND rip.impact_direction = 'negative') AS negative_impact_count,
    rp.created_at,
    rp.updated_at
FROM rotation_plan rp
JOIN location l ON l.id = rp.location_id
LEFT JOIN rotation_slot rs ON rs.plan_id = rp.id
LEFT JOIN crop_family cf ON cf.id = rs.crop_family_id
GROUP BY rp.id, rp.plan_name, rp.location_id, l.name, rp.plot_id,
         rp.zone_id, rp.duration_seasons, rp.start_season, rp.status,
         rp.created_at, rp.updated_at;

-- Impact records aggregated by type and direction
CREATE OR REPLACE VIEW v_rotation_impact_summary AS
SELECT
    rip.location_id,
    l.name AS location_name,
    rip.plan_id,
    rp.plan_name,
    rip.impact_type,
    rip.impact_direction,
    COUNT(*) AS record_count,
    AVG(rip.severity_pct) AS avg_severity_pct,
    MAX(rip.severity_pct) AS max_severity_pct,
    MIN(rip.record_date) AS first_recorded,
    MAX(rip.record_date) AS last_recorded,
    AVG(rip.measurement_value) AS avg_measurement_value,
    rip.measurement_unit
FROM rotation_impact_record rip
JOIN location l ON l.id = rip.location_id
LEFT JOIN rotation_plan rp ON rp.id = rip.plan_id
WHERE rip.status != 'dismissed'
GROUP BY rip.location_id, l.name, rip.plan_id, rp.plan_name,
         rip.impact_type, rip.impact_direction, rip.measurement_unit;

-- Crop family usage across locations, to detect over-repetition
CREATE OR REPLACE VIEW v_crop_family_usage AS
SELECT
    cf.id AS family_id,
    cf.family_name,
    cf.example_crops,
    rp.location_id,
    l.name AS location_name,
    rp.plan_name,
    rp.id AS plan_id,
    COUNT(rs.id) AS slot_count,
    ARRAY_AGG(rs.crop_name ORDER BY rs.season_number) AS crops_used,
    ARRAY_AGG(rs.season_number ORDER BY rs.season_number) AS seasons_used,
    (SELECT COUNT(DISTINCT rs2.plan_id)
     FROM rotation_slot rs2
     WHERE rs2.crop_family_id = cf.id) AS total_plans_using
FROM crop_family cf
LEFT JOIN rotation_slot rs ON rs.crop_family_id = cf.id
LEFT JOIN rotation_plan rp ON rp.id = rs.plan_id
LEFT JOIN location l ON l.id = rp.location_id
GROUP BY cf.id, cf.family_name, cf.example_crops,
         rp.location_id, l.name, rp.plan_name, rp.id;

-- ============================================================
-- SEED DATA: Common crop families
-- ============================================================

INSERT INTO crop_family (family_name, description, example_crops, notes) VALUES
    ('Fabaceae', 'Legumes — nitrogen-fixing family critical for rotation breaks and soil fertility',
     '["beans", "cowpeas", "groundnuts", "soybeans", "pigeon_peas", "lentils", "chickpeas", "clover"]',
     'Fix atmospheric nitrogen via Rhizobium root nodules. Break disease cycles for cereal crops.'),
    ('Poaceae', 'Grasses and cereals — primary staple and cash crop family',
     '["maize", "wheat", "rice", "sorghum", "millet", "barley", "oats", "sugarcane"]',
     'High nitrogen demand. Avoid consecutive seasons without nitrogen-fixing predecessor.'),
    ('Cucurbitaceae', 'Gourds and melons — sprawling crops often used as ground cover',
     '["cucumber", "pumpkin", "watermelon", "squash", "zucchini", "bitter_gourd", "melon"]',
     'Susceptible to similar pest complex; avoid back-to-back planting on same plot.'),
    ('Solanaceae', 'Nightshades — high-value but disease-prone family',
     '["tomato", "pepper", "eggplant", "potato"]',
     'Shared Verticillium and Fusarium susceptibility. Minimum 3-year break between solanaceous crops.'),
    ('Brassicaceae', 'Crucifers — fast-growing crops with biofumigation potential',
     '["cabbage", "kale", "cauliflower", "broccoli", "radish", "mustard", "turnip"]',
     'Glucosinolates may suppress soil-borne pathogens when incorporated as green manure.'),
    ('Convolvulaceae', 'Morning glory family — tuberous root crops',
     '["sweet_potato", "yam"]',
     'Good ground cover; shallow root system helps with soil structure. Low nutrient demand.'),
    ('Euphorbiaceae', 'Spurge family — industrial and root crop species',
     '["cassava", "castor_oil", "rubber"]',
     'Cassava is heavy feeder; allow soil recovery period. Long growing cycle limits rotation flexibility.')
ON CONFLICT (family_name) DO UPDATE SET
    description = EXCLUDED.description,
    example_crops = EXCLUDED.example_crops,
    notes = EXCLUDED.notes;
