-- ============================================================
-- 090_externality_countermeasures.sql — Externality Countermeasures
-- ============================================================

-- 1. Externality index (composite score per location per period)
CREATE TABLE IF NOT EXISTS externality_index (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_hidden_cost_usd NUMERIC(15,2) DEFAULT 0,
    externality_score NUMERIC(5,2) CHECK (externality_score >= 0 AND externality_score <= 100),
    severity VARCHAR(50),
    category_breakdown JSONB,
    natural_capital_impact NUMERIC(15,2) DEFAULT 0,
    social_impact NUMERIC(15,2) DEFAULT 0,
    environmental_impact NUMERIC(15,2) DEFAULT 0,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ei_location ON externality_index(location_id);
CREATE INDEX IF NOT EXISTS ei_period ON externality_index(period_start, period_end);
CREATE INDEX IF NOT EXISTS ei_severity ON externality_index(severity);

ALTER TABLE externality_index DROP CONSTRAINT IF EXISTS chk_ei_severity;
ALTER TABLE externality_index ADD CONSTRAINT chk_ei_severity CHECK (
    severity IS NULL OR severity IN ('negligible', 'low', 'moderate', 'high', 'critical')
);

-- 2. Externality alert
CREATE TABLE IF NOT EXISTS externality_alert (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    externality_index_id UUID REFERENCES externality_index(id) ON DELETE SET NULL,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    threshold_value NUMERIC(15,2),
    actual_value NUMERIC(15,2),
    status VARCHAR(50) DEFAULT 'open',
    acknowledged_by UUID,
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ea_location ON externality_alert(location_id);
CREATE INDEX IF NOT EXISTS ea_status ON externality_alert(status);
CREATE INDEX IF NOT EXISTS ea_severity ON externality_alert(severity);

ALTER TABLE externality_alert DROP CONSTRAINT IF EXISTS chk_ea_severity;
ALTER TABLE externality_alert ADD CONSTRAINT chk_ea_severity CHECK (severity IN ('info', 'warning', 'critical'));

ALTER TABLE externality_alert DROP CONSTRAINT IF EXISTS chk_ea_status;
ALTER TABLE externality_alert ADD CONSTRAINT chk_ea_status CHECK (status IN ('open', 'acknowledged', 'in_progress', 'resolved', 'false_positive'));

-- 3. Externality counteraction
CREATE TABLE IF NOT EXISTS externality_counteraction (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    externality_index_id UUID REFERENCES externality_index(id) ON DELETE SET NULL,
    alert_id UUID REFERENCES externality_alert(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    target_reduction_pct NUMERIC(5,2),
    progress_pct NUMERIC(5,2) DEFAULT 0,
    responsible_party VARCHAR(255),
    start_date DATE,
    target_date DATE,
    completion_date DATE,
    evidence_urls TEXT[],
    status VARCHAR(50) DEFAULT 'proposed',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ec_location ON externality_counteraction(location_id);
CREATE INDEX IF NOT EXISTS ec_status ON externality_counteraction(status);

ALTER TABLE externality_counteraction DROP CONSTRAINT IF EXISTS chk_ec_status;
ALTER TABLE externality_counteraction ADD CONSTRAINT chk_ec_status CHECK (status IN (
    'proposed', 'approved', 'in_progress', 'completed', 'cancelled'
));

-- 4. Externality reduction target
CREATE TABLE IF NOT EXISTS externality_reduction_target (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    externality_category VARCHAR(100) NOT NULL,
    baseline_score NUMERIC(5,2) NOT NULL,
    target_score NUMERIC(5,2) NOT NULL,
    target_date DATE NOT NULL,
    current_score NUMERIC(5,2),
    progress_pct NUMERIC(5,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ert_location ON externality_reduction_target(location_id);
CREATE INDEX IF NOT EXISTS ert_category ON externality_reduction_target(externality_category);

ALTER TABLE externality_reduction_target DROP CONSTRAINT IF EXISTS chk_ert_status;
ALTER TABLE externality_reduction_target ADD CONSTRAINT chk_ert_status CHECK (status IN ('active', 'achieved', 'missed', 'cancelled'));

-- 5. Public view
CREATE OR REPLACE VIEW v_public_externality_summary AS
SELECT
    ei.id,
    ei.location_id,
    l.name AS location_name,
    ei.period_start,
    ei.period_end,
    ei.total_hidden_cost_usd,
    ei.externality_score,
    ei.severity,
    ei.natural_capital_impact,
    ei.social_impact,
    ei.environmental_impact,
    ei.computed_at
FROM externality_index ei
JOIN location l ON l.id = ei.location_id
WHERE EXISTS (
    SELECT 1 FROM farm_registry_record fr
    WHERE fr.location_id = ei.location_id
    AND fr.status IN ('verified', 'published')
);
