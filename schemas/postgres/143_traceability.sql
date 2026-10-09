-- ============================================================
-- 143_traceability.sql — Supply Chain Traceability
-- Farm-to-fork provenance tracking, custody transfers,
-- quality inspections, certification verification, and
-- food safety compliance.
-- ============================================================

-- ============================================================
-- 1. Certification Type (reference)
-- ============================================================
CREATE TABLE IF NOT EXISTS certification_type (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    category        VARCHAR(50) NOT NULL,
    issuing_body    VARCHAR(200),
    validity_months INTEGER DEFAULT 12,
    description     TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cert_type_category ON certification_type(category);

COMMENT ON TABLE certification_type IS 'Reference data for certification standards (organic, fairtrade, Rainforest Alliance, etc.)';

-- ============================================================
-- 2. Quality Grade (reference)
-- ============================================================
CREATE TABLE IF NOT EXISTS quality_grade (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL UNIQUE,
    category    VARCHAR(50) NOT NULL,
    min_score   NUMERIC(5,2),
    max_score   NUMERIC(5,2),
    description TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE quality_grade IS 'Reference data for produce quality grading scales';

-- ============================================================
-- 3. Produce Batch
-- ============================================================
CREATE TABLE IF NOT EXISTS produce_batch (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    harvest_observation_id UUID REFERENCES harvest_yield_observation(id) ON DELETE SET NULL,
    batch_number        VARCHAR(100) NOT NULL,
    crop_name           VARCHAR(200) NOT NULL,
    variety             VARCHAR(200),
    quantity_kg         NUMERIC(12,4) NOT NULL,
    quantity_unit       VARCHAR(50) DEFAULT 'kg',
    harvest_date        DATE NOT NULL,
    grade               VARCHAR(50),
    origin_plot_id      UUID REFERENCES plot(id),
    origin_latitude     NUMERIC(10,7),
    origin_longitude    NUMERIC(10,7),
    origin_farm_name    VARCHAR(250),
    organic             BOOLEAN DEFAULT FALSE,
    status              VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'in_transit', 'delivered', 'consumed', 'rejected', 'expired')),
    expiry_date         DATE,
    notes               TEXT,
    source_system       TEXT,
    source_id           TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID,
    updated_by          UUID,
    CONSTRAINT uq_batch_number UNIQUE (batch_number)
);

CREATE INDEX IF NOT EXISTS idx_batch_location ON produce_batch(location_id);
CREATE INDEX IF NOT EXISTS idx_batch_harvest ON produce_batch(harvest_observation_id);
CREATE INDEX IF NOT EXISTS idx_batch_crop ON produce_batch(crop_name);
CREATE INDEX IF NOT EXISTS idx_batch_status ON produce_batch(status);
CREATE INDEX IF NOT EXISTS idx_batch_harvest_date ON produce_batch(harvest_date);

DROP TRIGGER IF EXISTS trg_produce_batch_updated_at ON produce_batch;
CREATE TRIGGER trg_produce_batch_updated_at
    BEFORE UPDATE ON produce_batch
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE produce_batch IS 'Produce batch created at harvest, linking to harvest_yield_observation for provenance tracking';

-- ============================================================
-- 4. Chain of Custody
-- ============================================================
CREATE TABLE IF NOT EXISTS chain_of_custody (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID NOT NULL REFERENCES produce_batch(id) ON DELETE CASCADE,
    sequence_num        INTEGER NOT NULL,
    from_actor_name     VARCHAR(250) NOT NULL,
    from_actor_type     VARCHAR(100) NOT NULL,
    from_actor_id       UUID,
    to_actor_name       VARCHAR(250) NOT NULL,
    to_actor_type       VARCHAR(100) NOT NULL,
    to_actor_id         UUID,
    transfer_date       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_date       TIMESTAMPTZ,
    quantity_kg         NUMERIC(12,4) NOT NULL,
    quantity_unit       VARCHAR(50) DEFAULT 'kg',
    transfer_method     VARCHAR(100),
    vehicle_id          VARCHAR(100),
    gps_latitude        NUMERIC(10,7),
    gps_longitude       NUMERIC(10,7),
    temperature_at_transfer_c NUMERIC(5,2),
    status              VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_transit', 'received', 'rejected', 'cancelled')),
    rejection_reason    TEXT,
    notes               TEXT,
    source_system       TEXT,
    source_id           TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID
);

CREATE INDEX IF NOT EXISTS idx_coc_batch ON chain_of_custody(batch_id);
CREATE INDEX IF NOT EXISTS idx_coc_from_actor ON chain_of_custody(from_actor_name);
CREATE INDEX IF NOT EXISTS idx_coc_to_actor ON chain_of_custody(to_actor_name);
CREATE INDEX IF NOT EXISTS idx_coc_status ON chain_of_custody(status);
CREATE INDEX IF NOT EXISTS idx_coc_transfer_date ON chain_of_custody(transfer_date);
CREATE INDEX IF NOT EXISTS idx_coc_sequence ON chain_of_custody(batch_id, sequence_num);

DROP TRIGGER IF EXISTS trg_coc_updated_at ON chain_of_custody;
CREATE TRIGGER trg_coc_updated_at
    BEFORE UPDATE ON chain_of_custody
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE chain_of_custody IS 'Custody transfers between actors (farmer, aggregator, processor, retailer) in the supply chain';

-- ============================================================
-- 5. Quality Inspection
-- ============================================================
CREATE TABLE IF NOT EXISTS quality_inspection (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID NOT NULL REFERENCES produce_batch(id) ON DELETE CASCADE,
    custody_id          UUID REFERENCES chain_of_custody(id) ON DELETE SET NULL,
    inspection_date     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    inspector_name      VARCHAR(250),
    inspector_org       VARCHAR(250),
    inspection_point    VARCHAR(100) NOT NULL
        CHECK (inspection_point IN ('harvest', 'receiving', 'processing', 'pre_dispatch', 'delivery', 'retail')),
    overall_grade       VARCHAR(50),
    score               NUMERIC(5,2)
        CHECK (score >= 0 AND score <= 100),
    moisture_pct        NUMERIC(5,2),
    foreign_material_pct NUMERIC(5,2),
    temperature_c       NUMERIC(5,2),
    appearance_score    NUMERIC(5,2),
    freshness_score     NUMERIC(5,2),
    size_uniformity     NUMERIC(5,2),
    defect_count        INTEGER DEFAULT 0,
    defect_notes        TEXT,
    passed              BOOLEAN NOT NULL DEFAULT TRUE,
    rejection_reason    TEXT,
    corrective_action   TEXT,
    evidence_urls       JSONB DEFAULT '[]'::jsonb,
    status              VARCHAR(50) NOT NULL DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'reviewed', 'escalated', 'closed')),
    notes               TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qi_batch ON quality_inspection(batch_id);
CREATE INDEX IF NOT EXISTS idx_qi_custody ON quality_inspection(custody_id);
CREATE INDEX IF NOT EXISTS idx_qi_inspection_date ON quality_inspection(inspection_date);
CREATE INDEX IF NOT EXISTS idx_qi_inspection_point ON quality_inspection(inspection_point);
CREATE INDEX IF NOT EXISTS idx_qi_passed ON quality_inspection(passed);
CREATE INDEX IF NOT EXISTS idx_qi_grade ON quality_inspection(overall_grade);

DROP TRIGGER IF EXISTS trg_qi_updated_at ON quality_inspection;
CREATE TRIGGER trg_qi_updated_at
    BEFORE UPDATE ON quality_inspection
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE quality_inspection IS 'Quality checks at each custody transfer point in the supply chain';

-- ============================================================
-- 6. Certification Verify
-- ============================================================
CREATE TABLE IF NOT EXISTS certification_verify (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id             UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    certification_type_id   UUID NOT NULL REFERENCES certification_type(id) ON DELETE RESTRICT,
    batch_id                UUID REFERENCES produce_batch(id) ON DELETE SET NULL,
    certificate_number      VARCHAR(200),
    issuing_body            VARCHAR(200) NOT NULL,
    issued_date             DATE NOT NULL,
    expiry_date             DATE,
    scope                   VARCHAR(100),
    scope_areas             JSONB DEFAULT '[]'::jsonb,
    verified                BOOLEAN DEFAULT FALSE,
    verified_by             VARCHAR(200),
    verified_at             TIMESTAMPTZ,
    chain_verified          BOOLEAN DEFAULT FALSE,
    onchain_tx_hash         VARCHAR(100),
    onchain_schema_uid      VARCHAR(100),
    document_url            TEXT,
    status                  VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'verified', 'expired', 'revoked', 'suspended')),
    notes                   TEXT,
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cv_location ON certification_verify(location_id);
CREATE INDEX IF NOT EXISTS idx_cv_type ON certification_verify(certification_type_id);
CREATE INDEX IF NOT EXISTS idx_cv_batch ON certification_verify(batch_id);
CREATE INDEX IF NOT EXISTS idx_cv_status ON certification_verify(status);
CREATE INDEX IF NOT EXISTS idx_cv_expiry ON certification_verify(expiry_date);

DROP TRIGGER IF EXISTS trg_cv_updated_at ON certification_verify;
CREATE TRIGGER trg_cv_updated_at
    BEFORE UPDATE ON certification_verify
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE certification_verify IS 'Verification of organic, fairtrade, Rainforest Alliance, and other certifications against supply chain batches';

-- ============================================================
-- 7. Provenance Event
-- ============================================================
CREATE TABLE IF NOT EXISTS provenance_event (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID NOT NULL REFERENCES produce_batch(id) ON DELETE CASCADE,
    event_type      VARCHAR(100) NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_name      VARCHAR(250),
    actor_type      VARCHAR(100),
    location_name   VARCHAR(250),
    gps_latitude    NUMERIC(10,7),
    gps_longitude   NUMERIC(10,7),
    description     TEXT,
    data            JSONB DEFAULT '{}',
    evidence_urls   JSONB DEFAULT '[]'::jsonb,
    chain_verified  BOOLEAN DEFAULT FALSE,
    onchain_tx_hash VARCHAR(100),
    immutable       BOOLEAN DEFAULT TRUE,
    status          VARCHAR(50) NOT NULL DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'verified', 'disputed')),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pe_batch ON provenance_event(batch_id);
CREATE INDEX IF NOT EXISTS idx_pe_event_type ON provenance_event(event_type);
CREATE INDEX IF NOT EXISTS idx_pe_event_time ON provenance_event(event_time);
CREATE INDEX IF NOT EXISTS idx_pe_status ON provenance_event(status);
CREATE INDEX IF NOT EXISTS idx_pe_chain ON provenance_event(chain_verified);

COMMENT ON TABLE provenance_event IS 'Immutable provenance events for farm-to-fork tracking (planting, harvest, transfer, processing, packaging, retail)';

-- ============================================================
-- 8. Food Safety Record
-- ============================================================
CREATE TABLE IF NOT EXISTS food_safety_record (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID NOT NULL REFERENCES produce_batch(id) ON DELETE CASCADE,
    custody_id          UUID REFERENCES chain_of_custody(id) ON DELETE SET NULL,
    record_type         VARCHAR(100) NOT NULL
        CHECK (record_type IN ('temperature_log', 'hygiene_check', 'pest_control', 'cleaning_log', 'allergen_check', 'haccp', 'other')),
    record_time         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_by         VARCHAR(200),
    location_name       VARCHAR(250),
    temperature_c       NUMERIC(5,2),
    temperature_min_c   NUMERIC(5,2),
    temperature_max_c   NUMERIC(5,2),
    within_range        BOOLEAN,
    humidity_pct        NUMERIC(5,2),
    ph_level            NUMERIC(4,2),
    hygiene_score       NUMERIC(5,2)
        CHECK (hygiene_score >= 0 AND hygiene_score <= 100),
    hand_wash_ok        BOOLEAN,
    protective_gear_ok  BOOLEAN,
    pest_detected       BOOLEAN DEFAULT FALSE,
    corrective_action   TEXT,
    passed              BOOLEAN NOT NULL DEFAULT TRUE,
    violation_notes     TEXT,
    evidence_urls       JSONB DEFAULT '[]'::jsonb,
    status              VARCHAR(50) NOT NULL DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'reviewed', 'escalated', 'closed')),
    notes               TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fs_batch ON food_safety_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_fs_custody ON food_safety_record(custody_id);
CREATE INDEX IF NOT EXISTS idx_fs_record_type ON food_safety_record(record_type);
CREATE INDEX IF NOT EXISTS idx_fs_record_time ON food_safety_record(record_time);
CREATE INDEX IF NOT EXISTS idx_fs_passed ON food_safety_record(passed);

COMMENT ON TABLE food_safety_record IS 'Food safety compliance records (temperature monitoring, hygiene checks, HACCP, pest control)';

-- ============================================================
-- Views
-- ============================================================

CREATE OR REPLACE VIEW v_batch_provenance AS
SELECT
    pb.id AS batch_id,
    pb.batch_number,
    pb.crop_name,
    pb.variety,
    pb.quantity_kg,
    pb.harvest_date,
    pb.grade AS harvest_grade,
    pb.origin_farm_name,
    pb.origin_latitude,
    pb.origin_longitude,
    pb.organic,
    pb.status AS batch_status,
    pb.created_at AS batch_created_at,
    (SELECT COUNT(*) FROM chain_of_custody coc WHERE coc.batch_id = pb.id) AS custody_transfers,
    (SELECT COUNT(*) FROM quality_inspection qi WHERE qi.batch_id = pb.id) AS inspection_count,
    (SELECT COUNT(*) FROM provenance_event pe WHERE pe.batch_id = pb.id) AS provenance_events,
    (SELECT COUNT(*) FROM food_safety_record fs WHERE fs.batch_id = pb.id) AS safety_records,
    (SELECT MAX(coc.transfer_date) FROM chain_of_custody coc WHERE coc.batch_id = pb.id) AS last_transfer_at,
    (SELECT coc.to_actor_name FROM chain_of_custody coc WHERE coc.batch_id = pb.id ORDER BY coc.sequence_num DESC LIMIT 1) AS current_holder
FROM produce_batch pb;

CREATE OR REPLACE VIEW v_certification_status AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    ct.name AS certification_name,
    ct.category AS certification_category,
    cv.certificate_number,
    cv.issuing_body,
    cv.issued_date,
    cv.expiry_date,
    cv.verified,
    cv.verified_at,
    cv.status,
    CASE
        WHEN cv.expiry_date IS NOT NULL AND cv.expiry_date < CURRENT_DATE THEN 'expired'
        WHEN cv.expiry_date IS NOT NULL AND cv.expiry_date < CURRENT_DATE + INTERVAL '30 days' THEN 'expiring_soon'
        ELSE cv.status
    END AS effective_status
FROM certification_verify cv
JOIN location l ON l.id = cv.location_id
JOIN certification_type ct ON ct.id = cv.certification_type_id
WHERE cv.status IN ('verified', 'pending')
ORDER BY l.name, ct.name;

CREATE OR REPLACE VIEW v_cold_chain_log AS
SELECT
    pb.id AS batch_id,
    pb.batch_number,
    pb.crop_name,
    coc.id AS custody_id,
    coc.from_actor_name,
    coc.to_actor_name,
    coc.transfer_date,
    coc.temperature_at_transfer_c,
    fs.record_time AS safety_record_time,
    fs.temperature_c AS recorded_temperature,
    fs.temperature_min_c,
    fs.temperature_max_c,
    fs.within_range,
    fs.humidity_pct,
    fs.recorded_by,
    fs.passed
FROM produce_batch pb
JOIN chain_of_custody coc ON coc.batch_id = pb.id
LEFT JOIN food_safety_record fs ON fs.batch_id = pb.id
    AND fs.record_type = 'temperature_log'
    AND fs.record_time BETWEEN coc.transfer_date - INTERVAL '2 hours' AND coc.transfer_date + INTERVAL '2 hours'
ORDER BY pb.batch_number, coc.sequence_num, fs.record_time;

-- ============================================================
-- Seed Data
-- ============================================================

DO $$
BEGIN
    -- Certification Types
    INSERT INTO certification_type (name, category, issuing_body, validity_months, description) VALUES
        ('USDA Organic', 'organic', 'USDA National Organic Program', 12, 'United States Department of Agriculture organic certification'),
        ('EU Organic', 'organic', 'European Commission', 12, 'European Union organic farming regulation (EU 2018/848)'),
        ('IFOAM Organic', 'organic', 'IFOAM Organics International', 12, 'International Federation of Organic Agriculture Movements standard'),
        ('Fairtrade Certified', 'fair_trade', 'Fairtrade International', 12, 'Fairtrade certification for equitable trade practices'),
        ('Fair Trade USA', 'fair_trade', 'Fair Trade USA', 12, 'Fair Trade USA certification'),
        ('Rainforest Alliance', 'sustainability', 'Rainforest Alliance', 12, 'Rainforest Alliance Certified seal for sustainable agriculture'),
        ('UTZ Certified', 'sustainability', 'UTZ', 12, 'UTZ program for sustainable farming (now part of Rainforest Alliance)'),
        ('GlobalG.A.P.', 'food_safety', 'GLOBALG.A.P.', 12, 'Good Agricultural Practices certification'),
        ('ISO 22000', 'food_safety', 'International Organization for Standardization', 36, 'Food safety management systems standard'),
        ('HACCP', 'food_safety', 'Codex Alimentarius', 12, 'Hazard Analysis Critical Control Points certification'),
        ('BRC Global Standard', 'food_safety', 'Brand Reputation Compliance', 12, 'British Retail Consortium global standard for food safety'),
        ('Kosher', 'specialty', 'Various rabbinical authorities', 12, 'Kosher dietary law certification'),
        ('Halal', 'specialty', 'Various Islamic certification bodies', 12, 'Halal dietary law certification')
    ON CONFLICT (name) DO UPDATE SET
        category = EXCLUDED.category,
        issuing_body = EXCLUDED.issuing_body,
        validity_months = EXCLUDED.validity_months,
        description = EXCLUDED.description;

    -- Quality Grades
    INSERT INTO quality_grade (name, category, min_score, max_score, description) VALUES
        ('Premium', 'grade', 90, 100, 'Highest quality, meets all premium market standards'),
        ('Grade A', 'grade', 80, 89.99, 'High quality, suitable for retail and export'),
        ('Grade B', 'grade', 70, 79.99, 'Good quality, suitable for local markets'),
        ('Grade C', 'grade', 60, 69.99, 'Fair quality, suitable for processing'),
        ('Grade D', 'grade', 50, 59.99, 'Below standard, limited market use'),
        ('Rejected', 'grade', 0, 49.99, 'Does not meet minimum quality standards'),
        ('Organic Premium', 'organic', 90, 100, 'Certified organic, premium grade'),
        ('Organic Standard', 'organic', 70, 89.99, 'Certified organic, standard grade'),
        ('Fairtrade Grade 1', 'fair_trade', 85, 100, 'Fairtrade certified, top grade'),
        ('Fairtrade Grade 2', 'fair_trade', 70, 84.99, 'Fairtrade certified, standard grade')
    ON CONFLICT (name) DO UPDATE SET
        category = EXCLUDED.category,
        min_score = EXCLUDED.min_score,
        max_score = EXCLUDED.max_score,
        description = EXCLUDED.description;
END $$;
