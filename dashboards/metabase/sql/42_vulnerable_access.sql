-- Vulnerable access dashboard: public-safe accommodations and participation pathway evidence.
SELECT
  l.name AS location,
  v.plan_date,
  v.access_scope,
  v.vulnerable_groups,
  v.access_barriers,
  v.accommodations,
  v.participation_pathways,
  v.accountable_role,
  v.implementation_status,
  v.access_coverage_pct,
  v.evidence_maturity,
  v.evidence_maturity_label,
  v.public_summary
FROM v_public_vulnerable_access_summary v
JOIN location l ON l.id = v.location_id
ORDER BY v.plan_date DESC, v.access_scope;
