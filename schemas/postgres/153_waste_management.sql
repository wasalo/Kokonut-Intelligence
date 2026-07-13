-- ============================================================
-- 153_waste_management.sql — Waste Management & Pollution Tracking
-- Waste streams, composting operations, recycling/reuse,
-- and pollution incident tracking for smallholder farms.
-- ============================================================

BEGIN;

-- ============================================================
-- Reference Data: Waste Types
-- ============================================================

CREATE TABLE IF NOT EXISTS waste_type (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(100) NOT NULL UNIQUE,
    name        VARCHAR(200) NOT NULL,
    category    VARCHAR(100) NOT NULL,
    description TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE waste_type IS 'Reference data for waste classification types';

-- ============================================================
-- Reference Data: Disposal Methods
-- ============================================================

CREATE TABLE IF NOT EXISTS disposal_method (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(100) NOT NULL UNIQUE,
    name        VARCHAR(200) NOT NULL,
    category    VARCHAR(100) NOT NULL,
    description TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE disposal_method IS 'Reference data for waste disposal methods';

-- ============================================================
-- 1. Waste Stream
-- ============================================================

CREATE TABLE IF NOT EXISTS waste_stream (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    waste_type      VARCHAR(100) NOT NULL,
    waste_name      VARCHAR(200) NOT NULL,
    quantity_kg     NUMERIC(10,2) NOT NULL,
    quantity_unit   VARCHAR(50) DEFAULT 'kg',
    record_date     DATE NOT NULL,
    disposal_method VARCHAR(100),
    notes           TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'recorded',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID,
    updated_by      UUID
);

CREATE INDEX IF NOT EXISTS idx_waste_stream_location ON waste_stream(location_id);
CREATE INDEX IF NOT EXISTS idx_waste_stream_type ON waste_stream(waste_type);
CREATE INDEX IF NOT EXISTS idx_waste_stream_disposal ON waste_stream(disposal_method);
CREATE INDEX IF NOT EXISTS idx_waste_stream_date ON waste_stream(record_date DESC);
CREATE INDEX IF NOT EXISTS idx_waste_stream_status ON waste_stream(status);
CREATE INDEX IF NOT EXISTS idx_waste_stream_loc_date ON waste_stream(location_id, record_date DESC);

ALTER TABLE waste_stream DROP CONSTRAINT IF EXISTS chk_waste_stream_type;
ALTER TABLE waste_stream ADD CONSTRAINT chk_waste_stream_type CHECK (waste_type IN (
    'crop_residue', 'processing_waste', 'packaging', 'chemical_container',
    'organic_waste', 'wastewater', 'other'
));

ALTER TABLE waste_stream DROP CONSTRAINT IF EXISTS chk_waste_stream_disposal;
ALTER TABLE waste_stream ADD CONSTRAINT chk_waste_stream_disposal CHECK (disposal_method IN (
    'composting', 'burning', 'landfill', 'recycling', 'animal_feed',
    'biogas', 'mulching', 'other'
));

ALTER TABLE waste_stream DROP CONSTRAINT IF EXISTS chk_waste_stream_status;
ALTER TABLE waste_stream ADD CONSTRAINT chk_waste_stream_status CHECK (status IN (
    'recorded', 'verified', 'archived'
));

-- ============================================================
-- 2. Composting Record
-- ============================================================

CREATE TABLE IF NOT EXISTS composting_record (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    compost_date        DATE NOT NULL,
    feedstock_type      VARCHAR(200) NOT NULL,
    feedstock_kg        NUMERIC(10,2) NOT NULL,
    compost_method      VARCHAR(100) NOT NULL,
    temperature_c       NUMERIC(5,1),
    moisture_pct        NUMERIC(5,1),
    duration_days        INTEGER,
    finished_volume_kg  NUMERIC(10,2),
    quality_grade       VARCHAR(50),
    application_plot_id UUID,
    notes               TEXT,
    status              VARCHAR(50) NOT NULL DEFAULT 'recorded',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID,
    updated_by          UUID
);

CREATE INDEX IF NOT EXISTS idx_composting_location ON composting_record(location_id);
CREATE INDEX IF NOT EXISTS idx_composting_date ON composting_record(compost_date DESC);
CREATE INDEX IF NOT EXISTS idx_composting_method ON composting_record(compost_method);
CREATE INDEX IF NOT EXISTS idx_composting_status ON composting_record(status);
CREATE INDEX IF NOT EXISTS idx_composting_feedstock ON composting_record(feedstock_type);
CREATE INDEX IF NOT EXISTS idx_composting_loc_date ON composting_record(location_id, compost_date DESC);

ALTER TABLE composting_record DROP CONSTRAINT IF EXISTS chk_composting_method;
ALTER TABLE composting_record ADD CONSTRAINT chk_composting_method CHECK (compost_method IN (
    'heap', 'pit', 'vermiculture', 'bokashi', 'other'
));

ALTER TABLE composting_record DROP CONSTRAINT IF EXISTS chk_composting_feedstock;
ALTER TABLE composting_record ADD CONSTRAINT chk_composting_feedstock CHECK (feedstock_type IN (
    'crop_residue', 'manure', 'food_waste', 'green_waste', 'mixed', 'other'
));

ALTER TABLE composting_record DROP CONSTRAINT IF EXISTS chk_composting_status;
ALTER TABLE composting_record ADD CONSTRAINT chk_composting_status CHECK (status IN (
    'recorded', 'verified', 'archived'
));

-- ============================================================
-- 3. Recycling Log
-- ============================================================

CREATE TABLE IF NOT EXISTS recycling_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    record_date     DATE NOT NULL,
    material_type   VARCHAR(100) NOT NULL,
    quantity_kg     NUMERIC(10,2) NOT NULL,
    destination     VARCHAR(200),
    revenue         NUMERIC(10,2),
    notes           TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'recorded',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID,
    updated_by      UUID
);

CREATE INDEX IF NOT EXISTS idx_recycling_location ON recycling_log(location_id);
CREATE INDEX IF NOT EXISTS idx_recycling_material ON recycling_log(material_type);
CREATE INDEX IF NOT EXISTS idx_recycling_date ON recycling_log(record_date DESC);
CREATE INDEX IF NOT EXISTS idx_recycling_status ON recycling_log(status);
CREATE INDEX IF NOT EXISTS idx_recycling_loc_date ON recycling_log(location_id, record_date DESC);

ALTER TABLE recycling_log DROP CONSTRAINT IF EXISTS chk_recycling_material;
ALTER TABLE recycling_log ADD CONSTRAINT chk_recycling_material CHECK (material_type IN (
    'plastic', 'metal', 'glass', 'paper', 'organic', 'other'
));

ALTER TABLE recycling_log DROP CONSTRAINT IF EXISTS chk_recycling_status;
ALTER TABLE recycling_log ADD CONSTRAINT chk_recycling_status CHECK (status IN (
    'recorded', 'verified', 'archived'
));

-- ============================================================
-- 4. Pollution Incident
-- ============================================================

CREATE TABLE IF NOT EXISTS pollution_incident (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    incident_date   DATE NOT NULL,
    incident_type   VARCHAR(100) NOT NULL,
    severity        VARCHAR(20) NOT NULL,
    description     TEXT NOT NULL,
    affected_area   VARCHAR(200),
    remedial_action TEXT,
    reported_to     VARCHAR(200),
    resolved        BOOLEAN DEFAULT FALSE,
    resolution_date DATE,
    notes           TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'open',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID,
    updated_by      UUID
);

CREATE INDEX IF NOT EXISTS idx_pollution_location ON pollution_incident(location_id);
CREATE INDEX IF NOT EXISTS idx_pollution_type ON pollution_incident(incident_type);
CREATE INDEX IF NOT EXISTS idx_pollution_severity ON pollution_incident(severity);
CREATE INDEX IF NOT EXISTS idx_pollution_date ON pollution_incident(incident_date DESC);
CREATE INDEX IF NOT EXISTS idx_pollution_status ON pollution_incident(status);
CREATE INDEX IF NOT EXISTS idx_pollution_open ON pollution_incident(status, severity) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_pollution_resolved ON pollution_incident(resolved);

ALTER TABLE pollution_incident DROP CONSTRAINT IF EXISTS chk_pollution_type;
ALTER TABLE pollution_incident ADD CONSTRAINT chk_pollution_type CHECK (incident_type IN (
    'chemical_spill', 'runoff', 'air_emission', 'water_contamination',
    'waste_dumping', 'other'
));

ALTER TABLE pollution_incident DROP CONSTRAINT IF EXISTS chk_pollution_severity;
ALTER TABLE pollution_incident ADD CONSTRAINT chk_pollution_severity CHECK (severity IN (
    'low', 'medium', 'high', 'critical'
));

ALTER TABLE pollution_incident DROP CONSTRAINT IF EXISTS chk_pollution_status;
ALTER TABLE pollution_incident ADD CONSTRAINT chk_pollution_status CHECK (status IN (
    'open', 'investigating', 'remediation', 'resolved', 'closed'
));

-- ============================================================
-- VIEWS
-- ============================================================

-- Waste totals by type and disposal method
CREATE OR REPLACE VIEW v_waste_summary AS
SELECT
    ws.location_id,
    l.name AS location_name,
    ws.waste_type,
    ws.disposal_method,
    ws.record_date,
    COUNT(*) AS record_count,
    SUM(ws.quantity_kg) AS total_kg,
    ROUND(AVG(ws.quantity_kg), 2) AS avg_quantity_kg,
    MIN(ws.record_date) AS first_record,
    MAX(ws.record_date) AS last_record
FROM waste_stream ws
JOIN location l ON l.id = ws.location_id
WHERE ws.status IN ('recorded', 'verified')
GROUP BY ws.location_id, l.name, ws.waste_type, ws.disposal_method, ws.record_date;

-- Composting yield and quality trends
CREATE OR REPLACE VIEW v_composting_efficiency AS
SELECT
    cr.location_id,
    l.name AS location_name,
    cr.compost_method,
    cr.feedstock_type,
    cr.compost_date,
    cr.feedstock_kg,
    cr.finished_volume_kg,
    CASE
        WHEN cr.feedstock_kg > 0 AND cr.finished_volume_kg IS NOT NULL
        THEN ROUND((cr.finished_volume_kg / cr.feedstock_kg * 100)::numeric, 1)
        ELSE NULL
    END AS yield_pct,
    cr.duration_days,
    cr.temperature_c,
    cr.moisture_pct,
    cr.quality_grade,
    cr.status
FROM composting_record cr
JOIN location l ON l.id = cr.location_id
WHERE cr.status IN ('recorded', 'verified');

-- Open pollution incidents with severity
CREATE OR REPLACE VIEW v_pollution_incidents AS
SELECT
    pi.id AS incident_id,
    pi.location_id,
    l.name AS location_name,
    pi.incident_date,
    pi.incident_type,
    pi.severity,
    pi.description,
    pi.affected_area,
    pi.remedial_action,
    pi.reported_to,
    pi.resolved,
    pi.resolution_date,
    pi.status,
    pi.created_at,
    pi.updated_at
FROM pollution_incident pi
JOIN location l ON l.id = pi.location_id
WHERE pi.status IN ('open', 'investigating', 'remediation')
ORDER BY
    CASE pi.severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END,
    pi.incident_date DESC;

COMMIT;

-- ============================================================
-- SEED DATA: Common waste types for smallholder farms
-- ============================================================

INSERT INTO waste_type (code, name, category, description) VALUES
    ('crop_residue', 'Crop Residue', 'organic', 'Stalks, husks, leaves, and other plant material left after harvest'),
    ('processing_waste', 'Processing Waste', 'organic', 'Waste from cleaning, sorting, or processing crops'),
    ('packaging', 'Packaging', 'inorganic', 'Plastic bags, cartons, wrapping materials from inputs or produce'),
    ('chemical_container', 'Chemical Container', 'hazardous', 'Empty pesticide, herbicide, or fertilizer containers'),
    ('organic_waste', 'Organic Waste', 'organic', 'Mixed organic material from farm or household'),
    ('wastewater', 'Wastewater', 'liquid', 'Water contaminated from washing, processing, or irrigation runoff'),
    ('plastic', 'Plastic', 'inorganic', 'Plastic films, bags, pipes, and other plastic materials'),
    ('metal', 'Metal', 'inorganic', 'Metal cans, wire, tool scraps, and ferrous/non-ferrous materials'),
    ('glass', 'Glass', 'inorganic', 'Broken glass, bottles, and other glass materials'),
    ('paper', 'Paper', 'inorganic', 'Cardboard, paper bags, and other paper-based materials'),
    ('e_waste', 'Electronic Waste', 'hazardous', 'Batteries, old phones, electronic components'),
    ('food_waste', 'Food Waste', 'organic', 'Spoiled or unsold produce and kitchen waste'),
    ('manure', 'Manure', 'organic', 'Animal waste from livestock operations'),
    ('green_waste', 'Green Waste', 'organic', 'Yard trimmings, grass clippings, garden debris')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    description = EXCLUDED.description;

-- ============================================================
-- SEED DATA: Common disposal methods for smallholder farms
-- ============================================================

INSERT INTO disposal_method (code, name, category, description) VALUES
    ('composting', 'Composting', 'recycling', 'Aerobic decomposition of organic waste into soil amendment'),
    ('burning', 'Open Burning', 'disposal', 'Burning of waste in open air (not recommended for hazardous materials)'),
    ('landfill', 'Landfill', 'disposal', 'Deposition at a designated landfill or dump site'),
    ('recycling', 'Recycling', 'recycling', 'Collection and reprocessing into new materials'),
    ('animal_feed', 'Animal Feed', 'reuse', 'Feeding suitable waste to livestock or poultry'),
    ('biogas', 'Biogas Production', 'energy', 'Anaerobic digestion to produce biogas and digestate'),
    ('mulching', 'Mulching', 'reuse', 'Spreading crop residue on soil surface to conserve moisture'),
    ('vermicomposting', 'Vermicomposting', 'recycling', 'Worm-based decomposition of organic waste'),
    ('bokashi', 'Bokashi Fermentation', 'recycling', 'Anaerobic fermentation using effective microorganisms'),
    ('reuse', 'Reuse', 'reuse', 'Direct reuse of material on-farm without processing'),
    ('hazardous_disposal', 'Hazardous Disposal', 'disposal', 'Professional disposal of hazardous materials at licensed facility'),
    ('septic', 'Septic System', 'liquid', 'On-site wastewater treatment via septic tank'),
    ('soak_pit', 'Soak Pit', 'liquid', 'Underground pit for absorbing greywater'),
    ('authorized_dump', 'Authorized Dump', 'disposal', 'Disposal at an authorized waste collection point')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    description = EXCLUDED.description;
