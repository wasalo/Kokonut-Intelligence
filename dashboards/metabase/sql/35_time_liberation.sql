-- Time liberation dashboard: public-safe time reclaimed and burden-reduction evidence.
SELECT
  l.name AS location,
  t.observation_date,
  t.workflow_area,
  t.baseline_hours,
  t.observed_hours,
  t.hours_reclaimed,
  t.burden_reduction_pct,
  t.automation_or_agent_used,
  t.automation_type,
  t.beneficiary_group,
  t.evidence_maturity,
  t.evidence_maturity_label,
  t.public_summary
FROM v_public_time_liberation_summary t
JOIN location l ON l.id = t.location_id
ORDER BY t.observation_date DESC, t.workflow_area;
