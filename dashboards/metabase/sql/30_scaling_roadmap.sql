-- Scaling roadmap dashboard: public-safe milestones, required resources, dependencies, and risk gates.
SELECT
  COALESCE(l.name, 'Network-level') AS location,
  s.roadmap_name,
  s.target_region,
  s.farm_model,
  s.planned_farm_count,
  s.capital_required_usd,
  s.partner_requirements,
  s.operational_dependencies,
  s.risk_gates,
  s.target_date,
  s.milestone_status,
  s.evidence_maturity,
  s.evidence_maturity_label,
  s.public_summary
FROM v_public_scaling_roadmap_summary s
LEFT JOIN location l ON l.id = s.location_id
ORDER BY s.target_date, s.roadmap_name;
