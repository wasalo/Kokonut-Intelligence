-- Replication readiness dashboard: barriers, enablers, support structures, and evidence maturity gates.
SELECT
  COALESCE(l.name, 'Network') AS source_location,
  r.assessment_date,
  r.target_region,
  r.farm_model,
  r.readiness_score,
  r.replication_status,
  r.ecological_prerequisites,
  r.cultural_governance_prerequisites,
  r.infrastructure_prerequisites,
  r.barriers,
  r.enablers,
  r.support_structures,
  r.minimum_evidence_maturity,
  r.minimum_evidence_maturity_label,
  r.evidence_maturity,
  r.evidence_maturity_label,
  r.public_summary
FROM v_public_replication_readiness_summary r
LEFT JOIN location l ON l.id = r.location_id
ORDER BY r.assessment_date DESC, r.target_region;
