-- ============================================================
-- 095_soil_protocol.sql — Soil Protocol, Mitigation, Reporting Cadence
-- ============================================================
-- Closes gaps 6 (soil sampling protocol), 10 (mitigation approach),
-- and 12/17 (reporting cadence).
-- ============================================================

-- 1. Sampling protocol (Gap 6)
CREATE TABLE IF NOT EXISTS sampling_protocol (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    protocol_key VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    domain VARCHAR(100) NOT NULL,
    sampling_design VARCHAR(100),
    sub_sample_count INTEGER DEFAULT 5,
    composite_sample_count INTEGER,
    target_depth_cm NUMERIC(6,2),
    depth_layer VARCHAR(50),
    exclusion_zones TEXT[] DEFAULT '{}',
    minimum_sample_mass_g INTEGER DEFAULT 500,
    collection_method VARCHAR(100),
    equipment_specification TEXT,
    container_type VARCHAR(50),
    preservative VARCHAR(100),
    max_transit_hours INTEGER DEFAULT 48,
    required_analyses TEXT[] DEFAULT '{}',
    analytical_method VARCHAR(255),
    lab_accreditation_required VARCHAR(255),
    qc_duplicate_frequency VARCHAR(50),
    qc_blank_frequency VARCHAR(50),
    range_validation_rules JSONB DEFAULT '{}',
    monitoring_frequency VARCHAR(50),
    event_triggered_conditions TEXT[] DEFAULT '{}',
    version VARCHAR(50) NOT NULL,
    effective_date DATE,
    review_cadence VARCHAR(50),
    owner_wallet VARCHAR(42),
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    UNIQUE(location_id, protocol_key)
);

CREATE INDEX IF NOT EXISTS sp_location ON sampling_protocol(location_id);
CREATE INDEX IF NOT EXISTS sp_domain ON sampling_protocol(domain);
CREATE INDEX IF NOT EXISTS sp_status ON sampling_protocol(status);

ALTER TABLE sampling_protocol DROP CONSTRAINT IF EXISTS chk_sp_domain;
ALTER TABLE sampling_protocol ADD CONSTRAINT chk_sp_domain CHECK (domain IN (
    'soil', 'soil_carbon', 'water', 'biodiversity', 'air', 'other'
));

ALTER TABLE sampling_protocol DROP CONSTRAINT IF EXISTS chk_sp_status;
ALTER TABLE sampling_protocol ADD CONSTRAINT chk_sp_status CHECK (status IN ('draft', 'active', 'archived'));

-- Enhance soil_sample with gold-standard fields (same as water_sample)
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS lab_accredited BOOLEAN DEFAULT FALSE;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS analytical_method VARCHAR(255);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS protocol_id UUID REFERENCES sampling_protocol(id);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS composite_count INTEGER;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS sub_sample_count INTEGER;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS gps_latitude NUMERIC(10,7);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS gps_longitude NUMERIC(10,7);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS collector_name VARCHAR(255);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS collector_id UUID REFERENCES staff(id);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS chain_of_custody TEXT;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS container_type VARCHAR(50);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS preservative VARCHAR(100);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS sample_mass_g INTEGER;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS moisture_conditions VARCHAR(50);

-- Enhance soil_carbon_measurement
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS lab_accredited BOOLEAN DEFAULT FALSE;
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS analytical_method VARCHAR(255);
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS protocol_id UUID REFERENCES sampling_protocol(id);

-- 2. Mitigation approach (Gap 10)
CREATE TABLE IF NOT EXISTS mitigation_approach (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    approach_key VARCHAR(100) NOT NULL,
    approach_name TEXT NOT NULL,
    mitigation_type VARCHAR(100) NOT NULL,
    source_table VARCHAR(100),
    source_id UUID,
    description TEXT NOT NULL,
    mechanism TEXT,
    affected_scope VARCHAR(100),
    affected_categories TEXT[] DEFAULT '{}',
    baseline_value NUMERIC(12,4),
    baseline_unit VARCHAR(50),
    target_reduction_pct NUMERIC(5,2),
    target_value NUMERIC(12,4),
    target_date DATE,
    measured_value NUMERIC(12,4),
    measured_date DATE,
    actual_reduction_pct NUMERIC(5,2),
    effectiveness_rating VARCHAR(50),
    estimated_cost_usd NUMERIC(18,2),
    actual_cost_usd NUMERIC(18,2),
    funding_source VARCHAR(255),
    responsible_role VARCHAR(100),
    responsible_party VARCHAR(255),
    start_date DATE,
    end_date DATE,
    reporting_obligation VARCHAR(255),
    reported BOOLEAN DEFAULT FALSE,
    reported_at TIMESTAMPTZ,
    evidence_urls TEXT[],
    evidence_hash VARCHAR(255),
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id_field VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    UNIQUE(location_id, approach_key)
);

CREATE INDEX IF NOT EXISTS ma_location ON mitigation_approach(location_id);
CREATE INDEX IF NOT EXISTS ma_type ON mitigation_approach(mitigation_type);
CREATE INDEX IF NOT EXISTS ma_source ON mitigation_approach(source_table, source_id);
CREATE INDEX IF NOT EXISTS ma_status ON mitigation_approach(status);
CREATE INDEX IF NOT EXISTS ma_target_date ON mitigation_approach(target_date);

ALTER TABLE mitigation_approach DROP CONSTRAINT IF EXISTS chk_ma_type;
ALTER TABLE mitigation_approach ADD CONSTRAINT chk_ma_type CHECK (mitigation_type IN (
    'emission_reduction', 'carbon_sequestration', 'adaptation',
    'externality_counteraction', 'risk_mitigation', 'loss_prevention',
    'efficiency_improvement', 'substitution', 'offset', 'other'
));

ALTER TABLE mitigation_approach DROP CONSTRAINT IF EXISTS chk_ma_status;
ALTER TABLE mitigation_approach ADD CONSTRAINT chk_ma_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE mitigation_approach DROP CONSTRAINT IF EXISTS chk_ma_effectiveness;
ALTER TABLE mitigation_approach ADD CONSTRAINT chk_ma_effectiveness CHECK (
    effectiveness_rating IS NULL OR effectiveness_rating IN ('high', 'moderate', 'low', 'insufficient_data', 'not_yet_measured')
);

-- 3. Reporting cadence (Gap 12/17)
CREATE TABLE IF NOT EXISTS reporting_cadence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    obligation_key VARCHAR(100) NOT NULL,
    obligation_name TEXT NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    framework_key VARCHAR(100),
    description TEXT NOT NULL,
    required_sections TEXT[] DEFAULT '{}',
    required_data_sources TEXT[] DEFAULT '{}',
    frequency VARCHAR(50) NOT NULL,
    frequency_detail VARCHAR(255),
    start_date DATE NOT NULL,
    end_date DATE,
    next_due_date DATE,
    last_completed_date DATE,
    grace_period_days INTEGER DEFAULT 7,
    overdue_count INTEGER DEFAULT 0,
    compliance_status VARCHAR(50) DEFAULT 'current',
    recipient_role VARCHAR(100),
    recipient_address VARCHAR(255),
    delivery_format VARCHAR(50),
    public_disclosure BOOLEAN DEFAULT FALSE,
    escalation_role VARCHAR(100),
    escalation_after_days INTEGER,
    auto_generate_report BOOLEAN DEFAULT FALSE,
    report_generator_command TEXT,
    owner_role VARCHAR(100),
    owner_wallet VARCHAR(42),
    review_cadence VARCHAR(50),
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    UNIQUE(location_id, obligation_key)
);

CREATE INDEX IF NOT EXISTS rc_location ON reporting_cadence(location_id);
CREATE INDEX IF NOT EXISTS rc_type ON reporting_cadence(report_type);
CREATE INDEX IF NOT EXISTS rc_next_due ON reporting_cadence(next_due_date);
CREATE INDEX IF NOT EXISTS rc_status ON reporting_cadence(status, compliance_status);

ALTER TABLE reporting_cadence DROP CONSTRAINT IF EXISTS chk_rc_type;
ALTER TABLE reporting_cadence ADD CONSTRAINT chk_rc_type CHECK (report_type IN (
    'grant_report', 'annual_impact', 'carbon_verification',
    'regulatory', 'internal_governance', 'public_disclosure',
    'on_chain_attestation', 'partner_report', 'community_update',
    'crisp_rating', 'financial_audit', 'other'
));

ALTER TABLE reporting_cadence DROP CONSTRAINT IF EXISTS chk_rc_frequency;
ALTER TABLE reporting_cadence ADD CONSTRAINT chk_rc_frequency CHECK (frequency IN (
    'weekly', 'monthly', 'quarterly', 'semi_annual', 'annual', 'event_triggered', 'on_demand'
));

ALTER TABLE reporting_cadence DROP CONSTRAINT IF EXISTS chk_rc_compliance;
ALTER TABLE reporting_cadence ADD CONSTRAINT chk_rc_compliance CHECK (
    compliance_status IN ('current', 'overdue', 'at_risk', 'suspended')
);

ALTER TABLE reporting_cadence DROP CONSTRAINT IF EXISTS chk_rc_status;
ALTER TABLE reporting_cadence ADD CONSTRAINT chk_rc_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));
