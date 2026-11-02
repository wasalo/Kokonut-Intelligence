-- Separate process maturity from portfolio-wide verified metric context.
-- Migration 196 joined every global metric to every process maturity row,
-- making portfolio aggregates appear to be process-specific outcomes.

BEGIN;

CREATE OR REPLACE VIEW v_process_outcome_correlation AS
SELECT
    pm.process_key,
    pm.name AS process_name,
    pmaturity.maturity_level,
    ml.name AS maturity_name,
    NULL::BIGINT AS metric_count,
    NULL::NUMERIC AS avg_metric_value,
    NULL::BIGINT AS location_count,
    'process_maturity'::VARCHAR(20) AS scope
FROM process_maturity pmaturity
JOIN process_map pm ON pm.process_key = pmaturity.process_key
JOIN process_maturity_level ml ON ml.level = pmaturity.maturity_level
GROUP BY pm.process_key, pm.name, pmaturity.maturity_level, ml.name

UNION ALL

SELECT
    NULL::VARCHAR(100) AS process_key,
    NULL::VARCHAR(255) AS process_name,
    NULL::INTEGER AS maturity_level,
    'Portfolio-wide verified metrics'::VARCHAR(100) AS maturity_name,
    COUNT(DISTINCT mv.id) AS metric_count,
    NULL::NUMERIC AS avg_metric_value,
    COUNT(DISTINCT mv.location_id) AS location_count,
    'portfolio_metrics'::VARCHAR(20) AS scope
FROM metric_value mv
WHERE mv.location_id IS NOT NULL
  AND mv.verified = TRUE;

COMMENT ON VIEW v_process_outcome_correlation IS
    'Separates process maturity rows from portfolio-wide verified metric context; metrics are not attributed to individual processes, and unlike metric units are not averaged together.';

COMMIT;
