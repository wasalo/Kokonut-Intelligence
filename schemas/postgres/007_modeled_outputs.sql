-- ============================================================
-- 007_modeled_outputs.sql — Forecasts, scenarios, reports
-- ============================================================

-- Forecast scenarios
CREATE TABLE IF NOT EXISTS forecast_scenario (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    scenario_type VARCHAR(50), -- optimistic, base, conservative, custom
    location_id UUID REFERENCES location(id),
    -- Assumptions
    assumptions JSONB NOT NULL DEFAULT '{}',
    -- Assumption details
    price_assumptions JSONB DEFAULT '{}',
    yield_assumptions JSONB DEFAULT '{}',
    cost_assumptions JSONB DEFAULT '{}',
    growth_assumptions JSONB DEFAULT '{}',
    -- Versioning
    version INTEGER DEFAULT 1,
    parent_scenario_id UUID REFERENCES forecast_scenario(id),
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Forecast outputs
CREATE TABLE IF NOT EXISTS forecast_output (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_id UUID NOT NULL REFERENCES forecast_scenario(id) ON DELETE CASCADE,
    location_id UUID REFERENCES location(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    -- Metric
    metric_name VARCHAR(100) NOT NULL, -- revenue, crop_noi, operating_margin, yield, cash_flow, etc.
    period_start DATE,
    period_end DATE,
    -- Value
    value NUMERIC(15,4),
    unit VARCHAR(50),
    -- Confidence intervals
    confidence_low NUMERIC(15,4),
    confidence_high NUMERIC(15,4),
    confidence_level NUMERIC(5,2), -- 0.90, 0.95, 0.99
    -- Metadata
    calculation_version VARCHAR(20),
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    inputs JSONB,
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_forecast_scenario ON forecast_output(scenario_id);
CREATE INDEX IF NOT EXISTS idx_forecast_location ON forecast_output(location_id);
CREATE INDEX IF NOT EXISTS idx_forecast_metric ON forecast_output(metric_name);
CREATE INDEX IF NOT EXISTS idx_forecast_period ON forecast_output(period_start, period_end);

-- Metric definitions (governed semantic layer)
CREATE TABLE IF NOT EXISTS metric_definition (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_key VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    formula TEXT,
    source_tables TEXT[],
    inclusion_rules TEXT,
    exclusion_rules TEXT,
    unit VARCHAR(50),
    data_type VARCHAR(50), -- numeric, percentage, currency, count
    owner VARCHAR(255),
    version INTEGER DEFAULT 1,
    update_frequency VARCHAR(50), -- real_time, hourly, daily, weekly, monthly, quarterly, annually
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Metric versions (change history)
CREATE TABLE IF NOT EXISTS metric_version (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_id UUID NOT NULL REFERENCES metric_definition(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    formula TEXT,
    changes TEXT,
    change_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    UNIQUE(metric_id, version)
);

-- Report snapshots (frozen report outputs)
CREATE TABLE IF NOT EXISTS report_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_name VARCHAR(255) NOT NULL,
    report_type VARCHAR(100), -- noi, cash_flow, environmental, impact, partner, public
    location_id UUID REFERENCES location(id),
    period_start DATE,
    period_end DATE,
    report_data JSONB NOT NULL,
    snapshot_hash VARCHAR(255),
    file_url TEXT,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_report_location ON report_snapshot(location_id);
CREATE INDEX IF NOT EXISTS idx_report_type ON report_snapshot(report_type);
CREATE INDEX IF NOT EXISTS idx_report_period ON report_snapshot(period_start, period_end);

-- Dashboard datasets (published data for BI/frontends)
CREATE TABLE IF NOT EXISTS dashboard_dataset (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    dataset_type VARCHAR(100), -- farm_operations, crop_noi, expenses, environmental, web3
    location_id UUID REFERENCES location(id),
    query_sql TEXT,
    refresh_interval_minutes INTEGER,
    last_refreshed_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by UUID
);

-- AI summaries (agent-generated narratives)
CREATE TABLE IF NOT EXISTS ai_summary (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_type VARCHAR(100) NOT NULL, -- location, crop_cycle, period, report
    subject_id UUID NOT NULL,
    summary_type VARCHAR(100), -- operations, financial, environmental, combined, anomaly
    content TEXT NOT NULL,
    source_record_ids UUID[],
    source_tables TEXT[],
    model_version VARCHAR(100),
    confidence NUMERIC(5,4),
    -- Review
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);
