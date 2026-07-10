-- ============================================================
-- 094_currency_stability.sql — Currency Stability Model
-- ============================================================

-- 1. Value stability metric
CREATE TABLE IF NOT EXISTS value_stability_metric (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    coin_value_estimate NUMERIC(15,6),
    economic_capacity_estimate NUMERIC(15,6),
    coins_per_capacity_ratio NUMERIC(10,6),
    inflation_rate NUMERIC(8,6),
    economic_growth_rate NUMERIC(8,6),
    deviation_from_target NUMERIC(8,6),
    target_value_growth_pct NUMERIC(8,4),
    status VARCHAR(50) DEFAULT 'computed',
    metadata JSONB DEFAULT '{}',
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS vsm_location ON value_stability_metric(location_id);
CREATE INDEX IF NOT EXISTS vsm_period ON value_stability_metric(period_start, period_end);

ALTER TABLE value_stability_metric DROP CONSTRAINT IF EXISTS chk_vsm_status;
ALTER TABLE value_stability_metric ADD CONSTRAINT chk_vsm_status CHECK (status IN ('computed', 'reviewed', 'actioned'));

-- 2. Inflation adjustment
CREATE TABLE IF NOT EXISTS inflation_adjustment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_id UUID REFERENCES inflation_schedule(id) ON DELETE SET NULL,
    previous_rate NUMERIC(8,6) NOT NULL,
    new_rate NUMERIC(8,6) NOT NULL,
    adjustment_reason TEXT NOT NULL,
    deviation_trigger NUMERIC(8,6),
    proposed_by VARCHAR(255),
    approved_by UUID,
    effective_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'proposed',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ia_schedule ON inflation_adjustment(schedule_id);
CREATE INDEX IF NOT EXISTS ia_status ON inflation_adjustment(status);

ALTER TABLE inflation_adjustment DROP CONSTRAINT IF EXISTS chk_ia_status;
ALTER TABLE inflation_adjustment ADD CONSTRAINT chk_ia_status CHECK (status IN ('proposed', 'approved', 'implemented', 'rejected'));

-- 3. Public view
CREATE OR REPLACE VIEW v_currency_stability_summary AS
SELECT
    vsm.id,
    vsm.location_id,
    l.name AS location_name,
    vsm.period_start,
    vsm.period_end,
    vsm.coin_value_estimate,
    vsm.economic_capacity_estimate,
    vsm.coins_per_capacity_ratio,
    vsm.inflation_rate,
    vsm.economic_growth_rate,
    vsm.deviation_from_target,
    vsm.status
FROM value_stability_metric vsm
LEFT JOIN location l ON l.id = vsm.location_id;
