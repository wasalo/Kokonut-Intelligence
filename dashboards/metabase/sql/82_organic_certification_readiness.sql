-- Organic certification readiness: overall readiness score, compliance, and transition status.
SELECT
  l.name AS location,
  ora.overall_readiness_score,
  ora.buffer_zone_compliance_pct,
  ora.harvest_segregation_compliance_pct,
  ora.input_audit_score,
  ora.prohibited_substance_score,
  ora.transition_phase,
  ora.assessment_date,
  otr.target_certification_date,
  otr.transition_start_date
FROM organic_readiness_assessment ora
JOIN location l ON l.id = ora.location_id
LEFT JOIN organic_transition_plan otr ON otr.location_id = ora.location_id AND otr.status = 'active'
WHERE ora.status = 'active'
ORDER BY ora.overall_readiness_score DESC;
