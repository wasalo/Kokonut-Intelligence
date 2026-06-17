-- Metric Version History — Initial version (v1) for all governed metrics
-- Copies formula from metric_definition into metric_version for audit trail

INSERT INTO metric_version (metric_id, version, formula, changes, change_reason)
SELECT
    md.id,
    1,
    md.formula,
    'Initial definition',
    'Seeded from metric_definition at platform initialization'
FROM metric_definition md
ON CONFLICT (metric_id, version) DO NOTHING;
