-- 060_scenario_parameters.sql
-- Scenario Parameters: Worst/Base/Best Case for All Model Parameters

BEGIN;

-- ============================================================================
-- SCENARIO PARAMETER
-- ============================================================================

CREATE TABLE IF NOT EXISTS scenario_parameter (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID NOT NULL REFERENCES forecast_scenario(id) ON DELETE CASCADE,
    parameter_key VARCHAR(100) NOT NULL,
    parameter_category VARCHAR(50) NOT NULL
        CHECK (parameter_category IN (
            'yield', 'price', 'cost', 'weather', 'ecological', 'governance', 'other'
        )),
    parameter_name VARCHAR(200) NOT NULL,
    description TEXT,
    unit VARCHAR(50),
    base_value NUMERIC(18,6) NOT NULL,
    worst_value NUMERIC(18,6) NOT NULL,
    best_value NUMERIC(18,6) NOT NULL,
    distribution VARCHAR(50) NOT NULL DEFAULT 'triangular'
        CHECK (distribution IN ('normal', 'uniform', 'triangular', 'lognormal', 'fixed')),
    std_deviation NUMERIC(18,6),
    min_bound NUMERIC(18,6),
    max_bound NUMERIC(18,6),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID,
    UNIQUE (scenario_id, parameter_key)
);

CREATE INDEX IF NOT EXISTS idx_scenario_param_scenario ON scenario_parameter(scenario_id);
CREATE INDEX IF NOT EXISTS idx_scenario_param_category ON scenario_parameter(parameter_category);
CREATE INDEX IF NOT EXISTS idx_scenario_param_key ON scenario_parameter(parameter_key);
CREATE INDEX IF NOT EXISTS idx_scenario_param_active ON scenario_parameter(is_active);

CREATE TRIGGER trg_scenario_parameter_updated_at
    BEFORE UPDATE ON scenario_parameter
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE scenario_parameter IS 'Worst/Base/Best case parameters for scenario modeling and Monte Carlo simulation';

-- ============================================================================
-- SCENARIO SIMULATION RESULT
-- ============================================================================

CREATE TABLE IF NOT EXISTS scenario_simulation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID NOT NULL REFERENCES forecast_scenario(id) ON DELETE CASCADE,
    simulation_type VARCHAR(50) NOT NULL
        CHECK (simulation_type IN ('monte_carlo', 'sensitivity', 'stress_test')),
    parameter_key VARCHAR(100),
    run_date DATE NOT NULL DEFAULT CURRENT_DATE,
    simulations_count INT,
    -- Summary statistics
    mean_noi_usd NUMERIC(18,2),
    median_noi_usd NUMERIC(18,2),
    std_dev_noi_usd NUMERIC(18,2),
    p10_noi_usd NUMERIC(18,2),
    p25_noi_usd NUMERIC(18,2),
    p75_noi_usd NUMERIC(18,2),
    p90_noi_usd NUMERIC(18,2),
    prob_negative_noi NUMERIC(5,4),
    value_at_risk_95 NUMERIC(18,2),
    -- Yield statistics
    mean_yield_tonnes NUMERIC(18,4),
    p10_yield_tonnes NUMERIC(18,4),
    p90_yield_tonnes NUMERIC(18,4),
    -- Revenue statistics
    mean_revenue_usd NUMERIC(18,2),
    p10_revenue_usd NUMERIC(18,2),
    p90_revenue_usd NUMERIC(18,2),
    -- Full distribution (JSONB array of values)
    noi_distribution JSONB,
    yield_distribution JSONB,
    revenue_distribution JSONB,
    -- Sensitivity-specific
    sensitivity_curve JSONB,
    -- Stress test-specific
    stress_type VARCHAR(100),
    stress_parameters JSONB,
    baseline_noi_usd NUMERIC(18,2),
    stressed_noi_usd NUMERIC(18,2),
    -- Metadata
    execution_time_ms INT,
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

CREATE INDEX IF NOT EXISTS idx_simulation_scenario ON scenario_simulation(scenario_id);
CREATE INDEX IF NOT EXISTS idx_simulation_type ON scenario_simulation(simulation_type);
CREATE INDEX IF NOT EXISTS idx_simulation_date ON scenario_simulation(run_date);

CREATE TRIGGER trg_scenario_simulation_updated_at
    BEFORE UPDATE ON scenario_simulation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE scenario_simulation IS 'Monte Carlo, sensitivity, and stress test simulation results for scenarios';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public scenario parameters
CREATE OR REPLACE VIEW v_public_scenario_parameters AS
SELECT
    sp.id,
    sp.scenario_id,
    fs.name AS scenario_name,
    fs.scenario_type,
    sp.parameter_key,
    sp.parameter_category,
    sp.parameter_name,
    sp.description,
    sp.unit,
    sp.base_value,
    sp.worst_value,
    sp.best_value,
    sp.distribution,
    sp.std_deviation,
    sp.min_bound,
    sp.max_bound,
    sp.is_active,
    CASE
        WHEN sp.best_value > sp.worst_value THEN 'positive_range'
        WHEN sp.best_value < sp.worst_value THEN 'negative_range'
        ELSE 'fixed'
    END AS range_direction,
    ROUND(((sp.best_value - sp.worst_value) / NULLIF(sp.base_value, 0) * 100)::numeric, 2) AS range_pct_of_base,
    sp.created_at
FROM scenario_parameter sp
JOIN forecast_scenario fs ON sp.scenario_id = fs.id
LEFT JOIN location l ON fs.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE sp.is_active = TRUE
  AND (fs.location_id IS NULL OR l.status IN ('active', 'verified', 'published'))
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 2. Public simulation results
CREATE OR REPLACE VIEW v_public_simulation_results AS
SELECT
    ss.id,
    ss.scenario_id,
    fs.name AS scenario_name,
    fs.scenario_type,
    ss.simulation_type,
    ss.parameter_key,
    ss.run_date,
    ss.simulations_count,
    ss.mean_noi_usd,
    ss.median_noi_usd,
    ss.std_dev_noi_usd,
    ss.p10_noi_usd,
    ss.p25_noi_usd,
    ss.p75_noi_usd,
    ss.p90_noi_usd,
    ss.prob_negative_noi,
    ss.value_at_risk_95,
    ss.mean_yield_tonnes,
    ss.mean_revenue_usd,
    ss.sensitivity_curve,
    ss.stress_type,
    ss.baseline_noi_usd,
    ss.stressed_noi_usd,
    CASE
        WHEN ss.simulation_type = 'sensitivity' THEN 'Parameter sensitivity analysis'
        WHEN ss.simulation_type = 'monte_carlo' THEN 'Stochastic simulation'
        WHEN ss.simulation_type = 'stress_test' THEN 'Stress test: ' || COALESCE(ss.stress_type, 'unknown')
        ELSE 'Unknown'
    END AS description,
    ss.created_at
FROM scenario_simulation ss
JOIN forecast_scenario fs ON ss.scenario_id = fs.id;

COMMIT;
