-- Fork opportunities: cross-domain insight transfers that could create high-value targets.
SELECT
  it.id AS transfer_id,
  it.source_domain,
  it.target_domain,
  it.event_type,
  it.transfer_status,
  it.confidence_score,
  it.created_at,
  dl.approval_status AS decision_status
FROM insight_transfer it
LEFT JOIN decision_log dl ON dl.correlation_id = it.correlation_id
WHERE it.transfer_status IN ('detected', 'pending_review')
ORDER BY it.confidence_score DESC NULLS LAST, it.created_at DESC;
