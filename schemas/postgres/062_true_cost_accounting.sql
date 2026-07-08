-- 062_true_cost_accounting.sql
-- True Cost Accounting & Triple Bottom Line Integration
-- 9 tables, 4 views across 5 phases

BEGIN;

-- ============================================================================
-- PHASE 1: HIDDEN COST ACCOUNTING
-- ============================================================================

CREATE TABLE IF NOT EXISTS hidden_cost_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    observation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    cost_category VARCHAR(100) NOT NULL
        CHECK (cost_category IN (
            'pollution', 'health', 'social', 'environmental', 'knowledge', 'intergenerational', 'other'
        )),
    cost_subcategory VARCHAR(100) NOT NULL
        CHECK (cost_subcategory IN (
            'water_pollution', 'soil_degradation', 'pesticide_exposure', 'cultural_erosion',
            'biodiversity_loss', 'habitat_fragmentation', 'air_pollution', 'noise_pollution',
            'waste_disposal', 'healthcare_cost', 'lost_labor_days', 'social_displacement',
            'knowledge_loss', 'resource_depletion', 'climate_damage', 'other'
        )),
    description TEXT NOT NULL,
    affected_population VARCHAR(200),
    monetary_estimate_usd NUMERIC(12,2) NOT NULL DEFAULT 0,
    valuation_method VARCHAR(100) NOT NULL DEFAULT 'market_price'
        CHECK (valuation_method IN (
            'market_price', 'replacement_cost', 'damage_cost', 'willingness_to_pay',
            'social_cost_of_carbon', 'benefit_transfer', 'integrated_valuation', 'other'
        )),
    uncertainty_level VARCHAR(50) NOT NULL DEFAULT 'medium'
        CHECK (uncertainty_level IN ('low', 'medium', 'high')),
    source_evidence JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'verified', 'published')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_hidden_cost_location ON hidden_cost_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_hidden_cost_category ON hidden_cost_observation(cost_category);
CREATE INDEX IF NOT EXISTS idx_hidden_cost_status ON hidden_cost_observation(status);

CREATE TRIGGER trg_hidden_cost_updated_at
    BEFORE UPDATE ON hidden_cost_observation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE hidden_cost_observation IS 'Tracks hidden costs (externalities) not reflected in market prices — pollution, health, social, environmental impacts with monetary estimates';

-- ============================================================================
-- PHASE 1: NATURAL CAPITAL VALUATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS natural_capital_valuation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    valuation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    capital_type VARCHAR(50) NOT NULL
        CHECK (capital_type IN (
            'carbon', 'biodiversity', 'water', 'soil', 'pollination', 'watershed', 'air_quality', 'other'
        )),
    service_description TEXT NOT NULL,
    quantity NUMERIC(18,6) NOT NULL DEFAULT 0,
    unit VARCHAR(50) NOT NULL,
    price_per_unit_usd NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_value_usd NUMERIC(12,2) GENERATED ALWAYS AS (quantity * price_per_unit_usd) STORED,
    valuation_method VARCHAR(100) NOT NULL DEFAULT 'market_price'
        CHECK (valuation_method IN (
            'market_price', 'replacement_cost', 'benefit_transfer', 'integrated_valuation', 'other'
        )),
    source_record_ids JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'verified', 'published')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_ncv_location ON natural_capital_valuation(location_id);
CREATE INDEX IF NOT EXISTS idx_ncv_type ON natural_capital_valuation(capital_type);
CREATE INDEX IF NOT EXISTS idx_ncv_status ON natural_capital_valuation(status);

CREATE TRIGGER trg_ncv_updated_at
    BEFORE UPDATE ON natural_capital_valuation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE natural_capital_valuation IS 'Unified monetary valuation of natural capital services (carbon, biodiversity, water, soil, pollination)';

-- ============================================================================
-- PHASE 2: SOCIAL IMPACT VALUATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS social_impact_valuation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    valuation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    impact_category VARCHAR(100) NOT NULL
        CHECK (impact_category IN (
            'training', 'governance', 'cultural_preservation', 'health',
            'community', 'gender_equity', 'education', 'other'
        )),
    impact_description TEXT NOT NULL,
    beneficiaries_count INT NOT NULL DEFAULT 0,
    monetary_value_usd NUMERIC(12,2) NOT NULL DEFAULT 0,
    valuation_method VARCHAR(100) NOT NULL DEFAULT 'replacement_cost'
        CHECK (valuation_method IN (
            'replacement_cost', 'benefit_transfer', 'stated_preference',
            'cost_avoidance', 'human_capital_method', 'other'
        )),
    source_record_ids JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'verified', 'published')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_siv_location ON social_impact_valuation(location_id);
CREATE INDEX IF NOT EXISTS idx_siv_category ON social_impact_valuation(impact_category);
CREATE INDEX IF NOT EXISTS idx_siv_status ON social_impact_valuation(status);

CREATE TRIGGER trg_siv_updated_at
    BEFORE UPDATE ON social_impact_valuation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE social_impact_valuation IS 'Monetary valuation of social capital improvements (training, governance, cultural preservation, health)';

-- ============================================================================
-- PHASE 2: WORKER SAFETY
-- ============================================================================

CREATE TABLE IF NOT EXISTS worker_safety_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    observation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    incident_type VARCHAR(100) NOT NULL
        CHECK (incident_type IN ('injury', 'near_miss', 'illness', 'exposure', 'other')),
    severity VARCHAR(50) NOT NULL DEFAULT 'minor'
        CHECK (severity IN ('minor', 'moderate', 'serious', 'critical')),
    description TEXT NOT NULL,
    affected_worker VARCHAR(200),
    root_cause TEXT,
    corrective_action TEXT,
    days_lost INT DEFAULT 0,
    medical_cost_usd NUMERIC(10,2) DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'investigating', 'resolved', 'closed')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_safety_location ON worker_safety_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_safety_type ON worker_safety_observation(incident_type);
CREATE INDEX IF NOT EXISTS idx_safety_status ON worker_safety_observation(status);

CREATE TRIGGER trg_safety_updated_at
    BEFORE UPDATE ON worker_safety_observation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE worker_safety_observation IS 'Workplace health and safety incident tracking';

-- ============================================================================
-- PHASE 2: LIVING WAGE BENCHMARK
-- ============================================================================

CREATE TABLE IF NOT EXISTS living_wage_benchmark (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    benchmark_date DATE NOT NULL DEFAULT CURRENT_DATE,
    country VARCHAR(100) NOT NULL,
    living_wage_hourly_usd NUMERIC(10,2) NOT NULL,
    minimum_wage_hourly_usd NUMERIC(10,2),
    source VARCHAR(200),
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'superseded')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_living_wage_location ON living_wage_benchmark(location_id);

CREATE TRIGGER trg_living_wage_updated_at
    BEFORE UPDATE ON living_wage_benchmark
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE living_wage_benchmark IS 'Living wage benchmarks for comparing wages paid vs living wage standards';

-- ============================================================================
-- PHASE 3: LIFE CYCLE ASSESSMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS lca_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    assessment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    lifecycle_stage VARCHAR(100) NOT NULL
        CHECK (lifecycle_stage IN (
            'input_production', 'cultivation', 'harvest', 'processing',
            'transport', 'packaging', 'disposal', 'other'
        )),
    input_type VARCHAR(200) NOT NULL,
    quantity NUMERIC(12,4) NOT NULL DEFAULT 0,
    unit VARCHAR(50) NOT NULL,
    carbon_footprint_kg_co2e NUMERIC(12,4) DEFAULT 0,
    water_footprint_liters NUMERIC(12,4) DEFAULT 0,
    energy_footprint_kwh NUMERIC(12,4) DEFAULT 0,
    waste_generated_kg NUMERIC(12,4) DEFAULT 0,
    source_record_ids JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'verified', 'published')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_lca_location ON lca_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_lca_stage ON lca_assessment(lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_lca_crop ON lca_assessment(crop_cycle_id);

CREATE TRIGGER trg_lca_updated_at
    BEFORE UPDATE ON lca_assessment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE lca_assessment IS 'Life cycle assessment tracking cradle-to-grave environmental impacts per product';

-- ============================================================================
-- PHASE 4: GRI INDICATOR MAPPING
-- ============================================================================

CREATE TABLE IF NOT EXISTS gri_indicator (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gri_code VARCHAR(20) NOT NULL UNIQUE,
    gri_standard VARCHAR(100) NOT NULL,
    indicator_name VARCHAR(200) NOT NULL,
    description TEXT,
    platform_metric_key VARCHAR(100),
    platform_table VARCHAR(100),
    platform_field VARCHAR(100),
    data_type VARCHAR(50) NOT NULL DEFAULT 'quantitative'
        CHECK (data_type IN ('quantitative', 'qualitative')),
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_gri_updated_at
    BEFORE UPDATE ON gri_indicator
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE gri_indicator IS 'Maps platform metrics to GRI (Global Reporting Initiative) standards for stakeholder reporting';

-- ============================================================================
-- PHASE 4: MATERIALITY ASSESSMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS materiality_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    assessment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    stakeholder_group VARCHAR(100) NOT NULL
        CHECK (stakeholder_group IN (
            'farmers', 'workers', 'community', 'funders', 'buyers', 'regulators', 'other'
        )),
    material_topic VARCHAR(200) NOT NULL,
    topic_category VARCHAR(100) NOT NULL
        CHECK (topic_category IN (
            'environmental', 'social', 'economic', 'governance', 'other'
        )),
    importance_to_stakeholder INT NOT NULL DEFAULT 3
        CHECK (importance_to_stakeholder BETWEEN 1 AND 5),
    importance_to_business INT NOT NULL DEFAULT 3
        CHECK (importance_to_business BETWEEN 1 AND 5),
    current_performance INT DEFAULT 3
        CHECK (current_performance BETWEEN 1 AND 5),
    priority_level VARCHAR(50) GENERATED ALWAYS AS (
        CASE
            WHEN importance_to_stakeholder >= 4 AND importance_to_business >= 4 THEN 'high'
            WHEN importance_to_stakeholder >= 3 OR importance_to_business >= 3 THEN 'medium'
            ELSE 'low'
        END
    ) STORED,
    notes TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_materiality_location ON materiality_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_materiality_priority ON materiality_assessment(priority_level);

CREATE TRIGGER trg_materiality_updated_at
    BEFORE UPDATE ON materiality_assessment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE materiality_assessment IS 'Stakeholder materiality assessment mapping stakeholder importance vs business importance';

-- ============================================================================
-- PHASE 5: CAPITAL FLOW OBSERVATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS capital_flow_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    observation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    from_capital VARCHAR(50) NOT NULL
        CHECK (from_capital IN ('natural', 'human', 'social', 'produced', 'financial')),
    to_capital VARCHAR(50) NOT NULL
        CHECK (to_capital IN ('natural', 'human', 'social', 'produced', 'financial')),
    flow_description TEXT NOT NULL,
    flow_value_usd NUMERIC(12,2) NOT NULL DEFAULT 0,
    flow_type VARCHAR(50) NOT NULL DEFAULT 'transfer'
        CHECK (flow_type IN ('investment', 'depletion', 'regeneration', 'transfer')),
    source_record_ids JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'verified', 'published')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_capital_flow_location ON capital_flow_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_capital_flow_from ON capital_flow_observation(from_capital);
CREATE INDEX IF NOT EXISTS idx_capital_flow_to ON capital_flow_observation(to_capital);

CREATE TRIGGER trg_capital_flow_updated_at
    BEFORE UPDATE ON capital_flow_observation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE capital_flow_observation IS 'Tracks transfers between natural, human, social, produced, and financial capitals';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public hidden costs summary
CREATE OR REPLACE VIEW v_public_hidden_costs AS
SELECT
    hco.id,
    hco.location_id,
    l.name AS location_name,
    hco.observation_date,
    hco.cost_category,
    hco.cost_subcategory,
    hco.description,
    hco.affected_population,
    hco.monetary_estimate_usd,
    hco.valuation_method,
    hco.uncertainty_level,
    hco.status,
    hco.created_at
FROM hidden_cost_observation hco
JOIN location l ON hco.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND hco.status IN ('verified', 'published');

-- 2. Public natural capital valuation
CREATE OR REPLACE VIEW v_public_natural_capital_valuation AS
SELECT
    ncv.id,
    ncv.location_id,
    l.name AS location_name,
    ncv.valuation_date,
    ncv.capital_type,
    ncv.service_description,
    ncv.quantity,
    ncv.unit,
    ncv.price_per_unit_usd,
    ncv.total_value_usd,
    ncv.valuation_method,
    ncv.status,
    ncv.created_at
FROM natural_capital_valuation ncv
JOIN location l ON ncv.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND ncv.status IN ('verified', 'published');

-- 3. Public social impact valuation
CREATE OR REPLACE VIEW v_public_social_impact_valuation AS
SELECT
    siv.id,
    siv.location_id,
    l.name AS location_name,
    siv.valuation_date,
    siv.impact_category,
    siv.impact_description,
    siv.beneficiaries_count,
    siv.monetary_value_usd,
    siv.valuation_method,
    siv.status,
    siv.created_at
FROM social_impact_valuation siv
JOIN location l ON siv.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND siv.status IN ('verified', 'published');

-- 4. True cost statement (market + hidden + capital values)
CREATE OR REPLACE VIEW v_true_cost_statement AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    -- Market costs (from financial data)
    (SELECT COALESCE(SUM(expense_event.amount), 0)
     FROM expense_event
     WHERE expense_event.location_id = l.id
       AND expense_event.status IN ('verified', 'published')
    ) AS market_costs_usd,
    -- Market revenue
    (SELECT COALESCE(SUM(revenue_event.amount_usd), 0)
     FROM revenue_event
     WHERE revenue_event.location_id = l.id
       AND revenue_event.status IN ('verified', 'published')
    ) AS market_revenue_usd,
    -- Hidden costs
    (SELECT COALESCE(SUM(hco.monetary_estimate_usd), 0)
     FROM hidden_cost_observation hco
     WHERE hco.location_id = l.id
       AND hco.status IN ('verified', 'published')
    ) AS hidden_costs_usd,
    -- Natural capital value
    (SELECT COALESCE(SUM(ncv.total_value_usd), 0)
     FROM natural_capital_valuation ncv
     WHERE ncv.location_id = l.id
       AND ncv.status IN ('verified', 'published')
    ) AS natural_capital_value_usd,
    -- Social capital value
    (SELECT COALESCE(SUM(siv.monetary_value_usd), 0)
     FROM social_impact_valuation siv
     WHERE siv.location_id = l.id
       AND siv.status IN ('verified', 'published')
    ) AS social_capital_value_usd,
    -- Computed fields
    (SELECT COALESCE(SUM(revenue_event.amount_usd), 0) - COALESCE(SUM(expense_event.amount), 0)
     FROM revenue_event
     CROSS JOIN expense_event
     WHERE revenue_event.location_id = l.id
       AND expense_event.location_id = l.id
       AND revenue_event.status IN ('verified', 'published')
       AND expense_event.status IN ('verified', 'published')
    ) AS market_profit_usd,
    -- True profit = market profit - hidden costs + capital values
    (
      (SELECT COALESCE(SUM(revenue_event.amount_usd), 0) - COALESCE(SUM(expense_event.amount), 0)
       FROM revenue_event CROSS JOIN expense_event
       WHERE revenue_event.location_id = l.id AND expense_event.location_id = l.id
         AND revenue_event.status IN ('verified', 'published')
         AND expense_event.status IN ('verified', 'published'))
      - (SELECT COALESCE(SUM(hco.monetary_estimate_usd), 0)
         FROM hidden_cost_observation hco
         WHERE hco.location_id = l.id AND hco.status IN ('verified', 'published'))
      + (SELECT COALESCE(SUM(ncv.total_value_usd), 0)
         FROM natural_capital_valuation ncv
         WHERE ncv.location_id = l.id AND ncv.status IN ('verified', 'published'))
      + (SELECT COALESCE(SUM(siv.monetary_value_usd), 0)
         FROM social_impact_valuation siv
         WHERE siv.location_id = l.id AND siv.status IN ('verified', 'published'))
    ) AS true_profit_usd,
    l.status
FROM location l
WHERE l.status IN ('active', 'verified', 'published');

COMMIT;
