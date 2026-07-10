-- ============================================================
-- 088_abundance_periodic.sql — Periodic Validation
-- ============================================================

-- 1. Periodic validation
CREATE TABLE IF NOT EXISTS periodic_validation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    estimate_id UUID NOT NULL REFERENCES impact_estimate_post(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    validation_type VARCHAR(50) DEFAULT 'realized_impact',
    status VARCHAR(50) DEFAULT 'pending',
    initiated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pv_estimate ON periodic_validation(estimate_id);
CREATE INDEX IF NOT EXISTS pv_period ON periodic_validation(period_start, period_end);
CREATE INDEX IF NOT EXISTS pv_status ON periodic_validation(status);

ALTER TABLE periodic_validation DROP CONSTRAINT IF EXISTS chk_pv_type;
ALTER TABLE periodic_validation ADD CONSTRAINT chk_pv_type CHECK (validation_type IN ('realized_impact', 'reassessment', 'audit'));

ALTER TABLE periodic_validation DROP CONSTRAINT IF EXISTS chk_pv_status;
ALTER TABLE periodic_validation ADD CONSTRAINT chk_pv_status CHECK (status IN (
    'pending', 'collecting_data', 'validating', 'validated', 'disputed', 'finalized'
));

-- 2. Realized impact record
CREATE TABLE IF NOT EXISTS realized_impact_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    validation_id UUID NOT NULL REFERENCES periodic_validation(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES expertise_category(id) ON DELETE RESTRICT,
    measured_value NUMERIC(12,4) NOT NULL,
    measurement_unit VARCHAR(50),
    measurement_date DATE NOT NULL,
    source_type VARCHAR(100),
    source_record_id UUID,
    source_evidence TEXT[],
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS rir_validation ON realized_impact_record(validation_id);
CREATE INDEX IF NOT EXISTS rir_category ON realized_impact_record(category_id);
CREATE INDEX IF NOT EXISTS rir_date ON realized_impact_record(measurement_date);

-- 3. Impact deviation
CREATE TABLE IF NOT EXISTS impact_deviation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    validation_id UUID NOT NULL REFERENCES periodic_validation(id) ON DELETE CASCADE,
    estimate_id UUID NOT NULL REFERENCES impact_estimate_post(id) ON DELETE RESTRICT,
    category_id UUID NOT NULL REFERENCES expertise_category(id) ON DELETE RESTRICT,
    estimated_value NUMERIC(12,4) NOT NULL,
    realized_value NUMERIC(12,4) NOT NULL,
    deviation_tonnes NUMERIC(12,4) NOT NULL,
    deviation_pct NUMERIC(8,4) NOT NULL,
    is_significant BOOLEAN DEFAULT FALSE,
    review_required BOOLEAN DEFAULT FALSE,
    reviewer_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    review_notes TEXT,
    status VARCHAR(50) DEFAULT 'computed',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS id_validation ON impact_deviation(validation_id);
CREATE INDEX IF NOT EXISTS id_category ON impact_deviation(category_id);
CREATE INDEX IF NOT EXISTS id_significant ON impact_deviation(is_significant);

ALTER TABLE impact_deviation DROP CONSTRAINT IF EXISTS chk_id_status;
ALTER TABLE impact_deviation ADD CONSTRAINT chk_id_status CHECK (status IN ('computed', 'reviewing', 'accepted', 'disputed', 'adjusted'));

-- 4. Relatedness coefficient
CREATE TABLE IF NOT EXISTS relatedness_coefficient (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_a_id UUID NOT NULL REFERENCES expertise_category(id) ON DELETE CASCADE,
    category_b_id UUID NOT NULL REFERENCES expertise_category(id) ON DELETE CASCADE,
    coefficient NUMERIC(5,4) NOT NULL CHECK (coefficient >= 0 AND coefficient <= 1),
    co_occurrence_count INTEGER DEFAULT 0,
    avg_impact_weight NUMERIC(8,4),
    computed_from_projects INTEGER DEFAULT 0,
    last_computed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(category_a_id, category_b_id)
);

CREATE INDEX IF NOT EXISTS rc_cat_a ON relatedness_coefficient(category_a_id);
CREATE INDEX IF NOT EXISTS rc_cat_b ON relatedness_coefficient(category_b_id);
