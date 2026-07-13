-- 149_pest_management.sql
-- Integrated Pest Management (IPM) module following EISA Integrated Farming Framework
-- Pest scouting, action thresholds, interventions, pesticide tracking, resistance monitoring, degree-day modeling

BEGIN;

-- ============================================================
-- PEST SCOUTING RECORDS
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_scouting_record (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id             UUID,
    zone_id             UUID,

    -- Scouting observation
    scout_date          DATE NOT NULL,
    pest_name           VARCHAR(200),
    pest_type           VARCHAR(50) CHECK (pest_type IN ('insect', 'weed', 'disease', 'nematode', 'other')),
    severity            VARCHAR(20) CHECK (severity IN ('none', 'low', 'moderate', 'high', 'severe')),
    incidence_pct       NUMERIC(5,2) CHECK (incidence_pct >= 0 AND incidence_pct <= 100),
    damage_pct          NUMERIC(5,2) CHECK (damage_pct >= 0 AND damage_pct <= 100),

    -- Beneficials and context
    beneficial_observed TEXT,
    weather_conditions  JSONB DEFAULT '{}',

    -- Evidence
    photo_url           TEXT,
    notes               TEXT,

    -- Provenance
    source_type         VARCHAR(50),
    source_system       VARCHAR(100),
    source_id           VARCHAR(200),

    -- Status & metadata
    status              VARCHAR(50) NOT NULL DEFAULT 'draft',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pest_scouting_location ON pest_scouting_record (location_id, scout_date DESC);
CREATE INDEX IF NOT EXISTS idx_pest_scouting_plot ON pest_scouting_record (plot_id);
CREATE INDEX IF NOT EXISTS idx_pest_scouting_zone ON pest_scouting_record (zone_id);
CREATE INDEX IF NOT EXISTS idx_pest_scouting_pest ON pest_scouting_record (pest_name, pest_type);
CREATE INDEX IF NOT EXISTS idx_pest_scouting_severity ON pest_scouting_record (severity) WHERE severity IN ('high', 'severe');
CREATE INDEX IF NOT EXISTS idx_pest_scouting_status ON pest_scouting_record (status);

-- ============================================================
-- ACTION THRESHOLDS
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_action_threshold (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id             UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,

    pest_name               VARCHAR(200) NOT NULL,
    crop_name               VARCHAR(100),

    -- Economic thresholds
    economic_injury_level   NUMERIC(10,2),  -- pest density at which cost of damage = cost of control
    economic_threshold      NUMERIC(10,2),  -- pest density at which action should be taken (below EIL)
    threshold_unit          VARCHAR(50),     -- per_leaf, per_plant, per_trap, per_m2

    notes                   TEXT,

    -- Status & metadata
    status                  VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pest_threshold_location ON pest_action_threshold (location_id, status);
CREATE INDEX IF NOT EXISTS idx_pest_threshold_pest ON pest_action_threshold (pest_name, crop_name);
CREATE INDEX IF NOT EXISTS idx_pest_threshold_active ON pest_action_threshold (pest_name) WHERE status = 'active';

-- ============================================================
-- PEST INTERVENTIONS (IPM ladder: biological → cultural → mechanical → chemical)
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_intervention (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    scouting_record_id  UUID REFERENCES pest_scouting_record(id) ON DELETE SET NULL,

    intervention_date   DATE NOT NULL,
    intervention_type   VARCHAR(50) NOT NULL CHECK (intervention_type IN (
        'biological', 'cultural', 'mechanical', 'chemical', 'semiochemical', 'genetic'
    )),
    method_name         VARCHAR(200),  -- e.g. "Bt spray", "trap crop", "hand picking", "neem oil"

    -- Target and application
    target_pest         VARCHAR(200),
    application_rate    NUMERIC(10,2),
    application_unit    VARCHAR(50),
    area_ha             NUMERIC(8,2),
    cost                NUMERIC(10,2),

    -- Effectiveness tracking
    effective           BOOLEAN,
    effectiveness_pct   NUMERIC(5,2) CHECK (effectiveness_pct >= 0 AND effectiveness_pct <= 100),

    notes               TEXT,

    -- Status & metadata
    status              VARCHAR(50) NOT NULL DEFAULT 'applied',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pest_intervention_location ON pest_intervention (location_id, intervention_date DESC);
CREATE INDEX IF NOT EXISTS idx_pest_intervention_scouting ON pest_intervention (scouting_record_id);
CREATE INDEX IF NOT EXISTS idx_pest_intervention_type ON pest_intervention (intervention_type, status);
CREATE INDEX IF NOT EXISTS idx_pest_intervention_pest ON pest_intervention (target_pest);
CREATE INDEX IF NOT EXISTS idx_pest_intervention_status ON pest_intervention (status);

-- ============================================================
-- PESTICIDE APPLICATION LOG (chemical use tracking for reduction monitoring)
-- ============================================================

CREATE TABLE IF NOT EXISTS pesticide_application_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,

    application_date    DATE NOT NULL,
    product_name        VARCHAR(200),
    active_ingredient   VARCHAR(200),
    chemical_class      VARCHAR(100),  -- organophosphate, pyrethroid, neonicotinoid, etc.

    -- Application details
    application_rate    NUMERIC(10,2),
    rate_unit           VARCHAR(50),
    area_ha             NUMERIC(8,2),
    total_volume        NUMERIC(10,2),
    volume_unit         VARCHAR(50),

    -- Safety intervals
    target_pest         VARCHAR(200),
    rei_days            INTEGER,  -- re-entry interval (days)
    phi_days            INTEGER,  -- pre-harvest interval (days)

    notes               TEXT,

    -- Status & metadata
    status              VARCHAR(50) NOT NULL DEFAULT 'applied',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pesticide_log_location ON pesticide_application_log (location_id, application_date DESC);
CREATE INDEX IF NOT EXISTS idx_pesticide_log_product ON pesticide_application_log (product_name);
CREATE INDEX IF NOT EXISTS idx_pesticide_log_ingredient ON pesticide_application_log (active_ingredient);
CREATE INDEX IF NOT EXISTS idx_pesticide_log_class ON pesticide_application_log (chemical_class);
CREATE INDEX IF NOT EXISTS idx_pesticide_log_status ON pesticide_application_log (status);

-- ============================================================
-- PEST RESISTANCE RECORDS
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_resistance_record (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,

    pest_name           VARCHAR(200),
    chemical_class      VARCHAR(100),
    resistance_level    VARCHAR(50) CHECK (resistance_level IN (
        'susceptible', 'low', 'moderate', 'high', 'confirmed'
    )),
    observation_date    DATE,
    notes               TEXT,

    -- Status & metadata
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pest_resistance_location ON pest_resistance_record (location_id, status);
CREATE INDEX IF NOT EXISTS idx_pest_resistance_pest ON pest_resistance_record (pest_name);
CREATE INDEX IF NOT EXISTS idx_pest_resistance_class ON pest_resistance_record (chemical_class);
CREATE INDEX IF NOT EXISTS idx_pest_resistance_level ON pest_resistance_record (resistance_level) WHERE resistance_level IN ('high', 'confirmed');

-- ============================================================
-- DEGREE-DAY RECORDS (temperature-based pest lifecycle modeling)
-- ============================================================

CREATE TABLE IF NOT EXISTS degree_day_record (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id             UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,

    record_date             DATE NOT NULL,
    base_temp               NUMERIC(5,2),  -- lower developmental threshold
    upper_temp              NUMERIC(5,2),  -- upper developmental threshold (optimal ceiling)

    max_temp                NUMERIC(5,2),
    min_temp                NUMERIC(5,2),
    degree_days             NUMERIC(8,2),  -- daily degree-day accumulation
    cumulative_degree_days  NUMERIC(10,2), -- running total for current lifecycle

    pest_name               VARCHAR(200),
    lifecycle_stage         VARCHAR(100),

    source                  VARCHAR(100),  -- weather_station, sensor, forecast

    -- Status & metadata
    status                  VARCHAR(50) NOT NULL DEFAULT 'recorded',
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_degree_day_location ON degree_day_record (location_id, record_date DESC);
CREATE INDEX IF NOT EXISTS idx_degree_day_pest ON degree_day_record (pest_name, record_date DESC);
CREATE INDEX IF NOT EXISTS idx_degree_day_stage ON degree_day_record (lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_degree_day_status ON degree_day_record (status);

-- ============================================================
-- VIEWS
-- ============================================================

-- Scouting summary with intervention counts
CREATE OR REPLACE VIEW v_pest_scouting_summary AS
SELECT
    psr.id AS scouting_id,
    psr.location_id,
    l.name AS location_name,
    psr.plot_id,
    psr.zone_id,
    psr.scout_date,
    psr.pest_name,
    psr.pest_type,
    psr.severity,
    psr.incidence_pct,
    psr.damage_pct,
    psr.beneficial_observed,
    psr.notes,
    psr.status,
    COUNT(pi.id) AS intervention_count,
    COUNT(pi.id) FILTER (WHERE pi.intervention_type = 'biological') AS bio_interventions,
    COUNT(pi.id) FILTER (WHERE pi.intervention_type = 'chemical') AS chem_interventions,
    COUNT(pi.id) FILTER (WHERE pi.intervention_type = 'mechanical') AS mech_interventions,
    COUNT(pi.id) FILTER (WHERE pi.intervention_type = 'cultural') AS cultural_interventions,
    MAX(pi.intervention_date) AS last_intervention_date,
    psr.created_at
FROM pest_scouting_record psr
JOIN location l ON l.id = psr.location_id
LEFT JOIN pest_intervention pi ON pi.scouting_record_id = psr.id
GROUP BY psr.id, l.name;

-- Chemical use totals by period, product, and class
CREATE OR REPLACE VIEW v_pesticide_usage AS
SELECT
    pal.location_id,
    l.name AS location_name,
    DATE_TRUNC('month', pal.application_date) AS usage_month,
    pal.product_name,
    pal.active_ingredient,
    pal.chemical_class,
    COUNT(*) AS application_count,
    SUM(COALESCE(pal.total_volume, 0)) AS total_volume_used,
    pal.volume_unit,
    SUM(COALESCE(pal.area_ha, 0)) AS total_area_treated,
    AVG(pal.rei_days) AS avg_rei_days,
    AVG(pal.phi_days) AS avg_phi_days
FROM pesticide_application_log pal
JOIN location l ON l.id = pal.location_id
WHERE pal.status = 'applied'
GROUP BY pal.location_id, l.name, DATE_TRUNC('month', pal.application_date),
         pal.product_name, pal.active_ingredient, pal.chemical_class, pal.volume_unit
ORDER BY usage_month DESC, total_volume_used DESC;

-- Cumulative degree days with pest lifecycle stage
CREATE OR REPLACE VIEW v_degree_day_tracking AS
SELECT
    ddr.location_id,
    l.name AS location_name,
    ddr.pest_name,
    ddr.record_date,
    ddr.base_temp,
    ddr.upper_temp,
    ddr.max_temp,
    ddr.min_temp,
    ddr.degree_days,
    ddr.cumulative_degree_days,
    ddr.lifecycle_stage,
    ddr.source,
    tat.economic_threshold AS action_threshold,
    tat.economic_injury_level,
    CASE
        WHEN ddr.cumulative_degree_days IS NOT NULL AND tat.economic_threshold IS NOT NULL
         AND ddr.cumulative_degree_days >= tat.economic_threshold THEN TRUE
        ELSE FALSE
    END AS threshold_exceeded,
    ddr.status
FROM degree_day_record ddr
JOIN location l ON l.id = ddr.location_id
LEFT JOIN pest_action_threshold tat
    ON tat.location_id = ddr.location_id
    AND tat.pest_name = ddr.pest_name
    AND tat.status = 'active'
ORDER BY ddr.location_id, ddr.pest_name, ddr.record_date DESC;

-- ============================================================
-- SEED DATA: Default action thresholds for common tropical pests
-- ============================================================

INSERT INTO pest_action_threshold (
    location_id, pest_name, crop_name,
    economic_injury_level, economic_threshold, threshold_unit,
    notes, status
)
SELECT
    l.id,
    t.pest_name,
    t.crop_name,
    t.economic_injury_level,
    t.economic_threshold,
    t.threshold_unit,
    t.notes,
    'active'
FROM location l
CROSS JOIN (VALUES
    -- Fall armyworm (Spodoptera frugiperda)
    ('fall_armyworm', 'maize',   2.0, 1.0, 'per_plant',
     'EIL based on 50% yield loss threshold; ET = 1 larva/plant for smallholder maize'),
    ('fall_armyworm', 'sorghum', 2.0, 1.0, 'per_plant',
     'Similar thresholds to maize; adjust for sorghum head stage'),
    ('fall_armyworm', 'rice',    3.0, 2.0, 'per_plant',
     'Lower damage potential on rice; monitor at tillering and heading stages'),

    -- Stem borer (Busseola fusca / Chilo partellus)
    ('stem_borer', 'maize',     10.0, 5.0, 'per_plant',
     'EIL based on 10% stem damage; ET at 5% dead hearts or bored stems'),
    ('stem_borer', 'sorghum',   10.0, 5.0, 'per_plant',
     'Monitor from tillering; higher tolerance in robust varieties'),

    -- Aphids (various species)
    ('aphids', 'maize',         50.0, 25.0, 'per_plant',
     'Colony count threshold; ET before honeydew/sooty mould causes secondary damage'),
    ('aphids', 'beans',         30.0, 15.0, 'per_plant',
     'Lower threshold for beans due to virus transmission risk'),
    ('aphids', 'tomato',        40.0, 20.0, 'per_plant',
     'Monitor for aphid-vectored viruses (CMV, TMV); ET based on colony count'),

    -- Whitefly (Bemisia tabaci)
    ('whitefly', 'tomato',      10.0, 5.0, 'per_leaf',
     'Critical for Tomato Yellow Leaf Curl Virus (TYLCV) management; sticky trap count'),
    ('whitefly', 'cassava',     15.0, 8.0, 'per_leaf',
     'Important for Cassava Mosaic Disease; monitor on lower leaf surface'),
    ('whitefly', 'beans',       10.0, 5.0, 'per_leaf',
     'ET based on yellow sticky trap catches or leaf counts')
) AS t(pest_name, crop_name, economic_injury_level, economic_threshold, threshold_unit, notes)
WHERE l.name IS NOT NULL
ON CONFLICT DO NOTHING;

-- ============================================================
-- SEED DATA: Common pest degree-day parameters
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_degree_day_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pest_name       VARCHAR(200) NOT NULL,
    base_temp       NUMERIC(5,2) NOT NULL,
    upper_temp      NUMERIC(5,2) NOT NULL,
    total_degree_days NUMERIC(8,2),  -- DD required for full lifecycle
    stages          JSONB DEFAULT '[]',  -- [{name, dd_start, dd_end}]
    notes           TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO pest_degree_day_config (pest_name, base_temp, upper_temp, total_degree_days, stages, notes) VALUES
    ('fall_armyworm',   10.0, 38.0, 550.0,
     '[{"name":"egg","dd_start":0,"dd_end":30},{"name":"larva","dd_start":30,"dd_end":350},{"name":"pupa","dd_start":350,"dd_end":430},{"name":"adult","dd_start":430,"dd_end":550}]',
     'Fall armyworm lifecycle parameters; base 10°C, optimal 25-30°C'),
    ('stem_borer',      10.0, 35.0, 600.0,
     '[{"name":"egg","dd_start":0,"dd_end":40},{"name":"larva","dd_start":40,"dd_end":400},{"name":"pupa","dd_start":400,"dd_end":480},{"name":"adult","dd_start":480,"dd_end":600}]',
     'Maize stem borer (Busseola fusca); base 10°C'),
    ('aphids',           5.0, 32.0, 120.0,
     '[{"name":"nymph","dd_start":0,"dd_end":80},{"name":"adult","dd_start":80,"dd_end":120}]',
     'Aphid rapid cycling; base 5°C, short generation time'),
    ('whitefly',        11.0, 35.0, 300.0,
     '[{"name":"egg","dd_start":0,"dd_end":50},{"name":"nymph","dd_start":50,"dd_end":220},{"name":"pupa","dd_start":220,"dd_end":270},{"name":"adult","dd_start":270,"dd_end":300}]',
     'Bemisia tabaci lifecycle; base 11°C')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Schema version
-- ============================================================

INSERT INTO schema_version (version, description, applied_by)
VALUES ('pest-management-v1', 'Integrated Pest Management: scouting, action thresholds, interventions, pesticide tracking, resistance monitoring, degree-day modeling', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;

COMMIT;
