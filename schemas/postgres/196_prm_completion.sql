-- 196_prm_completion.sql
-- PRM Completion: Customer Satisfaction + Total Cost of Ownership
-- Adds customer satisfaction tracking and TCO/correlation views.

BEGIN;

-- ============================================================
-- 1. customer_satisfaction
-- ============================================================
CREATE TABLE IF NOT EXISTS customer_satisfaction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    respondent_id UUID,
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    nps INTEGER CHECK (nps BETWEEN -10 AND 10),
    feedback TEXT,
    dimension VARCHAR(50) CHECK (dimension IN ('service', 'quality', 'timeliness', 'value', 'overall')),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cs_entity ON customer_satisfaction (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_cs_location ON customer_satisfaction (location_id);
CREATE INDEX IF NOT EXISTS idx_cs_recorded_at ON customer_satisfaction (recorded_at);
CREATE INDEX IF NOT EXISTS idx_cs_dimension ON customer_satisfaction (dimension);

COMMENT ON TABLE customer_satisfaction IS 'Per-interaction customer satisfaction scores with NPS and dimension breakdown.';

-- ============================================================
-- 2. v_total_cost_of_ownership
-- ============================================================
CREATE OR REPLACE VIEW v_total_cost_of_ownership AS
SELECT
    pm.process_key,
    pm.name AS process_name,
    pm.process_type,
    pm.location_id,
    date_trunc('month', pco.recorded_at) AS period,
    COUNT(DISTINCT pco.entity_id) AS instance_count,
    SUM(pco.cost_amount) AS total_cost,
    CASE WHEN COUNT(DISTINCT pco.entity_id) > 0
         THEN SUM(pco.cost_amount) / COUNT(DISTINCT pco.entity_id)
         ELSE 0 END AS cost_per_instance,
    pco.currency
FROM process_cost_observation pco
JOIN process_map pm ON pm.process_key = pco.process_key
GROUP BY pm.process_key, pm.name, pm.process_type, pm.location_id,
         date_trunc('month', pco.recorded_at), pco.currency;

COMMENT ON VIEW v_total_cost_of_ownership IS 'Monthly total cost of ownership aggregated by process, location, and currency.';

-- ============================================================
-- 3. v_process_outcome_correlation
-- ============================================================
CREATE OR REPLACE VIEW v_process_outcome_correlation AS
SELECT
    pm.process_key,
    pm.name AS process_name,
    pmaturity.maturity_level,
    ml.name AS maturity_name,
    COUNT(DISTINCT mv.id) AS metric_count,
    AVG(mv.value) AS avg_metric_value,
    COUNT(DISTINCT mv.location_id) AS location_count
FROM process_maturity pmaturity
JOIN process_map pm ON pm.process_key = pmaturity.process_key
JOIN process_maturity_level ml ON ml.level = pmaturity.maturity_level
LEFT JOIN metric_value mv ON mv.location_id IS NOT NULL
    AND mv.verified = TRUE
GROUP BY pm.process_key, pm.name, pmaturity.maturity_level, ml.name;

COMMENT ON VIEW v_process_outcome_correlation IS 'Correlates process maturity levels with verified metric outcomes.';

COMMIT;
