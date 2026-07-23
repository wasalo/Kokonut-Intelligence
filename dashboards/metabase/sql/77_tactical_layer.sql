-- Tactical layer: consolidated view of fork, pin, promotion ladder, and tactical opportunities.
SELECT
  'fork' AS tactic_type,
  it.source_domain,
  it.target_domain,
  it.transfer_status AS status,
  it.created_at
FROM insight_transfer it
WHERE it.transfer_status IN ('detected', 'pending_review')

UNION ALL

SELECT
  'pin' AS tactic_type,
  mv.metric_id::text AS source_domain,
  'unverified_metric' AS target_domain,
  'pending' AS status,
  mv.created_at
FROM metric_value mv
WHERE mv.verified = FALSE

UNION ALL

SELECT
  'promotion' AS tactic_type,
  'sensor_reading' AS source_domain,
  'metric_value' AS target_domain,
  CASE WHEN mv.verified THEN 'verified' ELSE 'draft' END AS status,
  mv.created_at
FROM metric_value mv
ORDER BY created_at DESC;
