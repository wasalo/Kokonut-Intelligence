-- 156_pest_biology.sql
-- Pest biology reference data, scouting schedules, compliance tracking
-- Extends 149_pest_management.sql with reference data and scheduling

BEGIN;

-- ============================================================
-- PEST BIOLOGY REFERENCE DATABASE
-- Reference data for tropical pest lifecycle parameters, hosts, natural enemies
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_biology_reference (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pest_name           VARCHAR(200) NOT NULL UNIQUE,
    scientific_name     VARCHAR(300),
    common_name         VARCHAR(200),
    pest_category       VARCHAR(100) CHECK (pest_category IN (
        'insect', 'mite', 'nematode', 'fungal', 'bacterial', 'viral', 'weed', 'rodent', 'other'
    )),

    -- Lifecycle parameters
    base_temp           NUMERIC(5,2) NOT NULL,
    upper_temp          NUMERIC(5,2) NOT NULL,
    total_degree_days   NUMERIC(8,2),
    stages              JSONB DEFAULT '[]',

    -- Ecology
    host_crops          JSONB DEFAULT '[]',
    natural_enemies     JSONB DEFAULT '[]',
    damage_description  TEXT,
    economic_importance VARCHAR(20) CHECK (economic_importance IN ('critical', 'high', 'moderate', 'low')),
    geographic_range    VARCHAR(200),

    notes               TEXT,
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pest_bio_name ON pest_biology_reference (pest_name);
CREATE INDEX IF NOT EXISTS idx_pest_bio_category ON pest_biology_reference (pest_category);
CREATE INDEX IF NOT EXISTS idx_pest_bio_hosts ON pest_biology_reference USING GIN (host_crops);
CREATE INDEX IF NOT EXISTS idx_pest_bio_importance ON pest_biology_reference (economic_importance);

-- ============================================================
-- SCOUTING SCHEDULES
-- Define when/how often to scout per pest and growth stage
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_scouting_schedule (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,

    pest_name           VARCHAR(200) NOT NULL,
    crop_name           VARCHAR(100),

    frequency_days      INTEGER NOT NULL DEFAULT 7,
    growth_stages       JSONB DEFAULT '[]',
    method              VARCHAR(100),
    sample_size         INTEGER,
    assigned_to         VARCHAR(200),
    start_date          DATE,
    end_date            DATE,

    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scout_schedule_location ON pest_scouting_schedule (location_id, status);
CREATE INDEX IF NOT EXISTS idx_scout_schedule_pest ON pest_scouting_schedule (pest_name);
CREATE INDEX IF NOT EXISTS idx_scout_schedule_active ON pest_scouting_schedule (location_id) WHERE status = 'active';

-- ============================================================
-- SCOUTING COMPLIANCE
-- Track whether scheduled scouting was completed on time
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_scouting_compliance (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id         UUID NOT NULL REFERENCES pest_scouting_schedule(id) ON DELETE CASCADE,

    scout_date          DATE NOT NULL,
    expected_date       DATE NOT NULL,
    status              VARCHAR(20) CHECK (status IN ('on_time', 'late', 'missed', 'skipped')),
    scouting_record_id  UUID REFERENCES pest_scouting_record(id) ON DELETE SET NULL,

    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scout_compliance_schedule ON pest_scouting_compliance (schedule_id, expected_date DESC);
CREATE INDEX IF NOT EXISTS idx_scout_compliance_status ON pest_scouting_compliance (status) WHERE status IN ('missed', 'late');

-- ============================================================
-- ALTER pest_intervention: add re-scout tracking columns
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'pest_intervention' AND column_name = 're_scout_date'
    ) THEN
        ALTER TABLE pest_intervention ADD COLUMN re_scout_date DATE;
        ALTER TABLE pest_intervention ADD COLUMN re_scout_record_id UUID REFERENCES pest_scouting_record(id) ON DELETE SET NULL;
        ALTER TABLE pest_intervention ADD COLUMN actual_effectiveness_pct NUMERIC(5,2) CHECK (actual_effectiveness_pct >= 0 AND actual_effectiveness_pct <= 100);
    END IF;
END $$;

-- ============================================================
-- PEST CROP INTERACTION MATRIX
-- Which pests attack which crops, severity by growth stage
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_crop_interaction (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pest_name           VARCHAR(200) NOT NULL,
    crop_name           VARCHAR(100) NOT NULL,

    damage_type         VARCHAR(100),
    severity_by_stage   JSONB DEFAULT '{}',
    yield_loss_potential NUMERIC(5,2) CHECK (yield_loss_potential >= 0 AND yield_loss_potential <= 100),
    peak_risk_stage     VARCHAR(100),
    preferred_management JSONB DEFAULT '[]',

    notes               TEXT,
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(pest_name, crop_name)
);

CREATE INDEX IF NOT EXISTS idx_pest_crop_pest ON pest_crop_interaction (pest_name);
CREATE INDEX IF NOT EXISTS idx_pest_crop_crop ON pest_crop_interaction (crop_name);

-- ============================================================
-- VIEWS
-- ============================================================

CREATE OR REPLACE VIEW v_scouting_compliance_summary AS
SELECT
    pss.location_id,
    pss.pest_name,
    pss.crop_name,
    pss.frequency_days,
    COUNT(psc.id) AS total_scheduled,
    COUNT(psc.id) FILTER (WHERE psc.status = 'on_time') AS completed_on_time,
    COUNT(psc.id) FILTER (WHERE psc.status = 'late') AS completed_late,
    COUNT(psc.id) FILTER (WHERE psc.status = 'missed') AS missed,
    COUNT(psc.id) FILTER (WHERE psc.status = 'skipped') AS skipped,
    CASE
        WHEN COUNT(psc.id) > 0 THEN
            ROUND(100.0 * COUNT(psc.id) FILTER (WHERE psc.status = 'on_time') / COUNT(psc.id), 1)
        ELSE NULL
    END AS compliance_pct
FROM pest_scouting_schedule pss
LEFT JOIN pest_scouting_compliance psc ON psc.schedule_id = pss.id
WHERE pss.status = 'active'
GROUP BY pss.id, pss.location_id, pss.pest_name, pss.crop_name, pss.frequency_days;

-- ============================================================
-- Schema version
-- ============================================================

INSERT INTO schema_version (version, description, applied_by)
VALUES ('pest-biology-v1', 'Pest biology reference, scouting schedules, compliance tracking, crop interactions', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;

COMMIT;
