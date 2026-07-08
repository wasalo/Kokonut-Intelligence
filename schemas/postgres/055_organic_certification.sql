-- 055_organic_certification.sql
-- Organic Certification Readiness & Compliance
-- Covers: USDA NOP, EU 2018/848, IFOAM standards

BEGIN;

-- ============================================================================
-- 1. ORGANIC CERTIFICATION RECORD
-- ============================================================================

CREATE TABLE IF NOT EXISTS organic_certification_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    standard VARCHAR(100) NOT NULL DEFAULT 'IFOAM',
    certification_type VARCHAR(50) NOT NULL DEFAULT 'initial'
        CHECK (certification_type IN ('initial', 'renewal', 'extension')),
    certification_body VARCHAR(200),
    application_date DATE,
    inspection_date DATE,
    certification_date DATE,
    expiration_date DATE,
    certificate_number VARCHAR(100),
    certificate_url TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'preparing', 'submitted', 'inspected', 'certified', 'suspended', 'revoked', 'expired')),
    scope VARCHAR(50) DEFAULT 'full'
        CHECK (scope IN ('full', 'partial', 'transitioning')),
    scope_areas JSONB DEFAULT '[]'::jsonb,
    annual_fee_usd NUMERIC(10,2),
    notes TEXT,
    evidence_urls JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_organic_cert_location ON organic_certification_record(location_id);
CREATE INDEX IF NOT EXISTS idx_organic_cert_status ON organic_certification_record(status);
CREATE INDEX IF NOT EXISTS idx_organic_cert_standard ON organic_certification_record(standard);

CREATE TRIGGER trg_organic_cert_updated_at
    BEFORE UPDATE ON organic_certification_record
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE organic_certification_record IS 'Tracks organic certification lifecycle per standard (USDA NOP, EU 2018/848, IFOAM)';

-- ============================================================================
-- 2. ORGANIC TRANSITION PLAN
-- ============================================================================

CREATE TABLE IF NOT EXISTS organic_transition_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    standard VARCHAR(100) NOT NULL DEFAULT 'IFOAM',
    transition_start_date DATE NOT NULL,
    expected_certification_date DATE,
    current_year INT NOT NULL DEFAULT 1
        CHECK (current_year BETWEEN 1 AND 5),
    total_years_required INT NOT NULL DEFAULT 3
        CHECK (total_years_required BETWEEN 2 AND 5),
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('planned', 'active', 'paused', 'completed', 'failed')),
    prohibited_substance_free_date DATE,
    buffer_zone_established_date DATE,
    record_keeping_ready_date DATE,
    training_completed_date DATE,
    organic_management_plan_date DATE,
    readiness_score NUMERIC(5,2) DEFAULT 0
        CHECK (readiness_score >= 0 AND readiness_score <= 100),
    barriers JSONB DEFAULT '[]'::jsonb,
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_transition_location ON organic_transition_plan(location_id);
CREATE INDEX IF NOT EXISTS idx_transition_status ON organic_transition_plan(status);
CREATE INDEX IF NOT EXISTS idx_transition_standard ON organic_transition_plan(standard);

CREATE TRIGGER trg_transition_updated_at
    BEFORE UPDATE ON organic_transition_plan
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE organic_transition_plan IS 'Tracks 2-3 year organic transition period with readiness scoring';

-- ============================================================================
-- 3. PROHIBITED SUBSTANCE RECORD
-- ============================================================================

CREATE TABLE IF NOT EXISTS prohibited_substance_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    substance_name VARCHAR(200) NOT NULL,
    substance_category VARCHAR(100) NOT NULL
        CHECK (substance_category IN (
            'synthetic_pesticide', 'synthetic_fertilizer', 'gmo_seed',
            'sewage_sludge', 'ionizing_radiation', 'prohibited_additive',
            'other'
        )),
    cas_number VARCHAR(50),
    date_used DATE NOT NULL,
    quantity NUMERIC(10,2),
    unit VARCHAR(20),
    reason_for_use TEXT,
    remediation_action TEXT,
    remediation_date DATE,
    withdrawal_period_days INT DEFAULT 0,
    withdrawal_end_date DATE,
    compliance_status VARCHAR(50) NOT NULL DEFAULT 'pending_remediation'
        CHECK (compliance_status IN ('cleared', 'violation', 'pending_remediation', 'under_review')),
    notes TEXT,
    evidence_urls JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_prohibited_location ON prohibited_substance_record(location_id);
CREATE INDEX IF NOT EXISTS idx_prohibited_status ON prohibited_substance_record(compliance_status);
CREATE INDEX IF NOT EXISTS idx_prohibited_category ON prohibited_substance_record(substance_category);

CREATE TRIGGER trg_prohibited_updated_at
    BEFORE UPDATE ON prohibited_substance_record
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE prohibited_substance_record IS 'Tracks prohibited substance usage during organic transition with withdrawal tracking';

-- ============================================================================
-- 4. BUFFER ZONE
-- ============================================================================

CREATE TABLE IF NOT EXISTS buffer_zone (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    buffer_name VARCHAR(200) NOT NULL,
    buffer_type VARCHAR(100) NOT NULL
        CHECK (buffer_type IN (
            'physical_fence', 'vegetative_barrier', 'uncultivated_strip',
            'water_barrier', 'road', 'hedgerow', 'other'
        )),
    width_m NUMERIC(6,2) NOT NULL CHECK (width_m > 0),
    length_m NUMERIC(8,2),
    area_m2 NUMERIC(10,2),
    adjacent_use VARCHAR(100)
        CHECK (adjacent_use IN (
            'conventional_farm', 'road', 'industrial', 'urban',
            'water_body', 'wildland', 'other'
        )),
    boundary_geometry GEOMETRY,
    establishment_date DATE,
    condition_status VARCHAR(50) NOT NULL DEFAULT 'adequate'
        CHECK (condition_status IN ('adequate', 'needs_repair', 'non_compliant')),
    last_inspection_date DATE,
    photos_urls JSONB DEFAULT '[]'::jsonb,
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_buffer_location ON buffer_zone(location_id);
CREATE INDEX IF NOT EXISTS idx_buffer_condition ON buffer_zone(condition_status);

CREATE TRIGGER trg_buffer_updated_at
    BEFORE UPDATE ON buffer_zone
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE buffer_zone IS 'Physical separation zones preventing contamination from non-organic adjacent areas';

-- ============================================================================
-- 5. ORGANIC INPUT AUDIT
-- ============================================================================

CREATE TABLE IF NOT EXISTS organic_input_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    application_date DATE NOT NULL,
    input_category VARCHAR(100) NOT NULL
        CHECK (input_category IN (
            'fertilizer', 'pesticide', 'fungicide', 'herbicide',
            'seed_treatment', 'soil_amendment', 'mulch', 'other'
        )),
    input_name VARCHAR(200) NOT NULL,
    input_source VARCHAR(50) NOT NULL DEFAULT 'purchased'
        CHECK (input_source IN ('on_farm', 'purchased', 'traded')),
    organic_certified BOOLEAN NOT NULL DEFAULT FALSE,
    supplier_name VARCHAR(200),
    supplier_organic_cert_url TEXT,
    quantity NUMERIC(10,2) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    application_method VARCHAR(100),
    target_pest_or_nutrient VARCHAR(200),
    pre_harvest_interval_days INT DEFAULT 0,
    reentry_interval_hours INT DEFAULT 0,
    is_prohibited BOOLEAN NOT NULL DEFAULT FALSE,
    prohibition_standard VARCHAR(100),
    notes TEXT,
    evidence_urls JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_input_audit_location ON organic_input_audit(location_id);
CREATE INDEX IF NOT EXISTS idx_input_audit_category ON organic_input_audit(input_category);
CREATE INDEX IF NOT EXISTS idx_input_audit_prohibited ON organic_input_audit(is_prohibited);
CREATE INDEX IF NOT EXISTS idx_input_audit_organic ON organic_input_audit(organic_certified);

CREATE TRIGGER trg_input_audit_updated_at
    BEFORE UPDATE ON organic_input_audit
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE organic_input_audit IS 'Comprehensive input audit trail for organic certification — fertilizer, pesticide, herbicide, seed tracking';

-- ============================================================================
-- 6. HARVEST HANDLING RECORD
-- ============================================================================

CREATE TABLE IF NOT EXISTS harvest_handling_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    harvest_event_id UUID NOT NULL REFERENCES harvest_event(id) ON DELETE CASCADE,
    handling_date DATE NOT NULL,
    handling_type VARCHAR(100) NOT NULL
        CHECK (handling_type IN (
            'cleaning', 'sorting', 'grading', 'drying',
            'processing', 'packaging', 'storage', 'transport'
        )),
    organic_segregated BOOLEAN NOT NULL DEFAULT TRUE,
    equipment_cleaned BOOLEAN NOT NULL DEFAULT TRUE,
    contamination_risk VARCHAR(50) NOT NULL DEFAULT 'low'
        CHECK (contamination_risk IN ('low', 'medium', 'high')),
    temperature_controlled BOOLEAN NOT NULL DEFAULT FALSE,
    storage_conditions VARCHAR(200),
    transport_conditions VARCHAR(200),
    organic_lot_number VARCHAR(100),
    buyer_requirements_met BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    evidence_urls JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_harvest_handling_location ON harvest_handling_record(location_id);
CREATE INDEX IF NOT EXISTS idx_harvest_handling_harvest ON harvest_handling_record(harvest_event_id);
CREATE INDEX IF NOT EXISTS idx_harvest_handling_segregated ON harvest_handling_record(organic_segregated);

CREATE TRIGGER trg_harvest_handling_updated_at
    BEFORE UPDATE ON harvest_handling_record
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE harvest_handling_record IS 'Post-harvest organic compliance — segregation, traceability, and handling protocols';

-- ============================================================================
-- 7. ORGANIC COMPLIANCE CHECKLIST
-- ============================================================================

CREATE TABLE IF NOT EXISTS organic_compliance_checklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    certification_record_id UUID REFERENCES organic_certification_record(id) ON DELETE SET NULL,
    inspection_date DATE NOT NULL,
    inspector_name VARCHAR(200),
    inspector_organization VARCHAR(200),
    inspection_type VARCHAR(50) NOT NULL DEFAULT 'initial'
        CHECK (inspection_type IN ('initial', 'renewal', 'follow_up', 'unannounced')),
    checklist_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    findings TEXT,
    non_conformances JSONB DEFAULT '[]'::jsonb,
    corrective_actions_required JSONB DEFAULT '[]'::jsonb,
    follow_up_date DATE,
    overall_result VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (overall_result IN ('pass', 'conditional', 'fail', 'pending')),
    notes TEXT,
    evidence_urls JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_checklist_location ON organic_compliance_checklist(location_id);
CREATE INDEX IF NOT EXISTS idx_checklist_cert ON organic_compliance_checklist(certification_record_id);
CREATE INDEX IF NOT EXISTS idx_checklist_result ON organic_compliance_checklist(overall_result);

CREATE TRIGGER trg_checklist_updated_at
    BEFORE UPDATE ON organic_compliance_checklist
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE organic_compliance_checklist IS 'Structured inspection checklist per organic certification standard requirement';

-- ============================================================================
-- 8. ORGANIC READINESS ASSESSMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS organic_readiness_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    assessment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    standard VARCHAR(100) NOT NULL DEFAULT 'IFOAM',
    overall_score NUMERIC(5,2) NOT NULL DEFAULT 0
        CHECK (overall_score >= 0 AND overall_score <= 100),
    transition_progress_pct NUMERIC(5,2) DEFAULT 0
        CHECK (transition_progress_pct >= 0 AND transition_progress_pct <= 100),
    soil_health_score NUMERIC(5,2) DEFAULT 0
        CHECK (soil_health_score >= 0 AND soil_health_score <= 100),
    input_compliance_pct NUMERIC(5,2) DEFAULT 0
        CHECK (input_compliance_pct >= 0 AND input_compliance_pct <= 100),
    pest_management_score NUMERIC(5,2) DEFAULT 0
        CHECK (pest_management_score >= 0 AND pest_management_score <= 100),
    biodiversity_score NUMERIC(5,2) DEFAULT 0
        CHECK (biodiversity_score >= 0 AND biodiversity_score <= 100),
    buffer_zone_score NUMERIC(5,2) DEFAULT 0
        CHECK (buffer_zone_score >= 0 AND buffer_zone_score <= 100),
    record_completeness_pct NUMERIC(5,2) DEFAULT 0
        CHECK (record_completeness_pct >= 0 AND record_completeness_pct <= 100),
    training_completion_pct NUMERIC(5,2) DEFAULT 0
        CHECK (training_completion_pct >= 0 AND training_completion_pct <= 100),
    harvest_segregation_score NUMERIC(5,2) DEFAULT 0
        CHECK (harvest_segregation_score >= 0 AND harvest_segregation_score <= 100),
    barriers JSONB DEFAULT '[]'::jsonb,
    recommendations JSONB DEFAULT '[]'::jsonb,
    assessor VARCHAR(200),
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_readiness_location ON organic_readiness_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_readiness_standard ON organic_readiness_assessment(standard);

CREATE TRIGGER trg_readiness_updated_at
    BEFORE UPDATE ON organic_readiness_assessment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE organic_readiness_assessment IS 'Composite organic certification readiness scoring across 8 dimensions';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public organic readiness
CREATE OR REPLACE VIEW v_public_organic_readiness AS
SELECT
    r.id,
    r.location_id,
    l.name AS location_name,
    l.latitude,
    l.longitude,
    fr.id AS farm_registry_id,
    fr.status AS farm_status,
    r.assessment_date,
    r.standard,
    r.overall_score,
    r.transition_progress_pct,
    r.soil_health_score,
    r.input_compliance_pct,
    r.pest_management_score,
    r.biodiversity_score,
    r.buffer_zone_score,
    r.record_completeness_pct,
    r.training_completion_pct,
    r.harvest_segregation_score,
    r.barriers,
    r.recommendations,
    r.assessor,
    r.notes,
    r.created_at
FROM organic_readiness_assessment r
JOIN location l ON r.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 2. Public organic transition
CREATE OR REPLACE VIEW v_public_organic_transition AS
SELECT
    t.id,
    t.location_id,
    l.name AS location_name,
    l.latitude,
    l.longitude,
    fr.id AS farm_registry_id,
    fr.status AS farm_status,
    t.standard,
    t.transition_start_date,
    t.expected_certification_date,
    t.current_year,
    t.total_years_required,
    t.status,
    ROUND((t.current_year::numeric / t.total_years_required) * 100, 1) AS progress_pct,
    t.prohibited_substance_free_date,
    t.buffer_zone_established_date,
    t.record_keeping_ready_date,
    t.training_completed_date,
    t.organic_management_plan_date,
    t.readiness_score,
    t.barriers,
    t.notes,
    t.created_at
FROM organic_transition_plan t
JOIN location l ON t.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 3. Public organic certifications
CREATE OR REPLACE VIEW v_public_organic_certifications AS
SELECT
    c.id,
    c.location_id,
    l.name AS location_name,
    l.latitude,
    l.longitude,
    fr.id AS farm_registry_id,
    fr.status AS farm_status,
    c.standard,
    c.certification_type,
    c.certification_body,
    c.application_date,
    c.inspection_date,
    c.certification_date,
    c.expiration_date,
    c.certificate_number,
    c.status,
    c.scope,
    c.scope_areas,
    c.annual_fee_usd,
    c.notes,
    c.created_at
FROM organic_certification_record c
JOIN location l ON c.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 4. Public prohibited substance audit
CREATE OR REPLACE VIEW v_public_prohibited_substance_audit AS
SELECT
    p.id,
    p.location_id,
    l.name AS location_name,
    fr.id AS farm_registry_id,
    p.substance_name,
    p.substance_category,
    p.cas_number,
    p.date_used,
    p.quantity,
    p.unit,
    p.remediation_action,
    p.remediation_date,
    p.withdrawal_end_date,
    p.compliance_status,
    CASE
        WHEN p.withdrawal_end_date IS NOT NULL AND p.withdrawal_end_date <= CURRENT_DATE THEN 'cleared'
        WHEN p.withdrawal_end_date IS NULL AND p.compliance_status = 'cleared' THEN 'cleared'
        ELSE 'pending'
    END AS clearance_status,
    p.notes,
    p.created_at
FROM prohibited_substance_record p
JOIN location l ON p.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 5. Public buffer zone status
CREATE OR REPLACE VIEW v_public_buffer_zone_status AS
SELECT
    b.id,
    b.location_id,
    l.name AS location_name,
    fr.id AS farm_registry_id,
    b.buffer_name,
    b.buffer_type,
    b.width_m,
    b.length_m,
    b.area_m2,
    b.adjacent_use,
    b.establishment_date,
    b.condition_status,
    b.last_inspection_date,
    CASE
        WHEN b.width_m >= 5 THEN 'exceeds_minimum'
        WHEN b.width_m >= 3 THEN 'meets_minimum'
        ELSE 'below_minimum'
    END AS adequacy_status,
    b.notes,
    b.created_at
FROM buffer_zone b
JOIN location l ON b.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 6. Public organic input audit
CREATE OR REPLACE VIEW v_public_organic_input_audit AS
SELECT
    a.id,
    a.location_id,
    l.name AS location_name,
    fr.id AS farm_registry_id,
    a.application_date,
    a.input_category,
    a.input_name,
    a.input_source,
    a.organic_certified,
    a.supplier_name,
    a.quantity,
    a.unit,
    a.application_method,
    a.target_pest_or_nutrient,
    a.pre_harvest_interval_days,
    a.reentry_interval_hours,
    a.is_prohibited,
    a.prohibition_standard,
    a.notes,
    a.created_at
FROM organic_input_audit a
JOIN location l ON a.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 7. Public harvest segregation
CREATE OR REPLACE VIEW v_public_harvest_segregation AS
SELECT
    h.id,
    h.location_id,
    l.name AS location_name,
    fr.id AS farm_registry_id,
    h.harvest_event_id,
    h.handling_date,
    h.handling_type,
    h.organic_segregated,
    h.equipment_cleaned,
    h.contamination_risk,
    h.temperature_controlled,
    h.organic_lot_number,
    h.buyer_requirements_met,
    h.storage_conditions,
    h.notes,
    h.created_at
FROM harvest_handling_record h
JOIN location l ON h.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 8. Consolidated organic compliance dashboard
CREATE OR REPLACE VIEW v_public_organic_compliance_dashboard AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    l.latitude,
    l.longitude,
    fr.id AS farm_registry_id,
    fr.status AS farm_status,
    -- Certification status
    (SELECT c.standard FROM organic_certification_record c
     WHERE c.location_id = l.id ORDER BY c.created_at DESC LIMIT 1) AS active_standard,
    (SELECT c.status FROM organic_certification_record c
     WHERE c.location_id = l.id ORDER BY c.created_at DESC LIMIT 1) AS certification_status,
    (SELECT c.expiration_date FROM organic_certification_record c
     WHERE c.location_id = l.id ORDER BY c.created_at DESC LIMIT 1) AS certification_expiry,
    -- Transition progress
    (SELECT t.status FROM organic_transition_plan t
     WHERE t.location_id = l.id AND t.status = 'active' LIMIT 1) AS transition_status,
    (SELECT t.current_year FROM organic_transition_plan t
     WHERE t.location_id = l.id AND t.status = 'active' LIMIT 1) AS transition_year,
    (SELECT t.total_years_required FROM organic_transition_plan t
     WHERE t.location_id = l.id AND t.status = 'active' LIMIT 1) AS transition_total_years,
    -- Prohibited substances
    (SELECT COUNT(*)::int FROM prohibited_substance_record p
     WHERE p.location_id = l.id) AS total_prohibited_substances,
    (SELECT COUNT(*)::int FROM prohibited_substance_record p
     WHERE p.location_id = l.id AND p.compliance_status = 'cleared') AS cleared_substances,
    (SELECT COUNT(*)::int FROM prohibited_substance_record p
     WHERE p.location_id = l.id AND p.compliance_status = 'pending_remediation') AS pending_substances,
    -- Buffer zones
    (SELECT COUNT(*)::int FROM buffer_zone b
     WHERE b.location_id = l.id) AS buffer_zone_count,
    (SELECT COUNT(*)::int FROM buffer_zone b
     WHERE b.location_id = l.id AND b.condition_status = 'adequate') AS adequate_buffers,
    -- Input compliance
    (SELECT COUNT(*)::int FROM organic_input_audit a
     WHERE a.location_id = l.id) AS total_inputs,
    (SELECT COUNT(*)::int FROM organic_input_audit a
     WHERE a.location_id = l.id AND a.organic_certified = TRUE) AS organic_inputs,
    (SELECT COUNT(*)::int FROM organic_input_audit a
     WHERE a.location_id = l.id AND a.is_prohibited = TRUE) AS prohibited_inputs,
    -- Harvest segregation
    (SELECT COUNT(*)::int FROM harvest_handling_record h
     WHERE h.location_id = l.id) AS total_harvests,
    (SELECT COUNT(*)::int FROM harvest_handling_record h
     WHERE h.location_id = l.id AND h.organic_segregated = TRUE) AS segregated_harvests,
    -- Latest readiness
    (SELECT r.overall_score FROM organic_readiness_assessment r
     WHERE r.location_id = l.id ORDER BY r.assessment_date DESC LIMIT 1) AS latest_readiness_score,
    (SELECT r.assessment_date FROM organic_readiness_assessment r
     WHERE r.location_id = l.id ORDER BY r.assessment_date DESC LIMIT 1) AS latest_readiness_date,
    -- Compliance checklist
    (SELECT c.overall_result FROM organic_compliance_checklist c
     WHERE c.location_id = l.id ORDER BY c.inspection_date DESC LIMIT 1) AS latest_inspection_result
FROM location l
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

COMMIT;
