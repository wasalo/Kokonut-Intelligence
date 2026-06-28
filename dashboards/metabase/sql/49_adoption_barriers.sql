-- Adoption barriers dashboard: category, severity, owner, mitigation, and resolution status.
SELECT
  COALESCE(l.name, 'Network') AS source_location,
  b.assessment_date,
  b.barrier_category,
  b.barrier_name,
  b.affected_scope,
  b.severity,
  b.likelihood,
  b.resolution_status,
  b.owner_role,
  b.estimated_mitigation_cost_usd,
  b.target_resolution_date,
  b.evidence_maturity,
  b.evidence_maturity_label,
  b.public_summary
FROM v_public_adoption_barrier_assessment b
LEFT JOIN location l ON l.id = b.location_id
ORDER BY b.assessment_date DESC, b.severity DESC, b.barrier_category;
