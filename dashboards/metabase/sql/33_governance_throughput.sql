-- Governance throughput dashboard: public-safe proposal latency and execution traceability.
SELECT
  COALESCE(l.name, 'Network') AS location,
  g.proposal_code,
  g.venue,
  g.proposal_type,
  g.proposal_created_at,
  g.decision_at,
  g.executed_at,
  g.decision_latency_days,
  g.execution_latency_days,
  g.decision_result,
  g.evidence_maturity,
  g.evidence_maturity_label,
  g.public_summary
FROM v_public_governance_throughput_summary g
LEFT JOIN location l ON l.id = g.location_id
ORDER BY g.proposal_created_at DESC, g.proposal_code;
