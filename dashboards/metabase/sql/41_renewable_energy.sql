-- Renewable energy dashboard: public-safe planned and implemented renewable infrastructure evidence.
SELECT
  l.name AS location,
  r.plan_date,
  r.energy_use_case,
  r.renewable_source,
  r.implementation_status,
  r.current_energy_source,
  r.planned_capacity_kw,
  r.estimated_annual_kwh,
  r.renewable_share_pct,
  r.fossil_displacement_estimate_co2e_tonnes,
  r.infrastructure_dependencies,
  r.maintenance_owner_role,
  r.evidence_maturity,
  r.evidence_maturity_label,
  r.public_summary
FROM v_public_renewable_energy_summary r
JOIN location l ON l.id = r.location_id
ORDER BY r.plan_date DESC, r.energy_use_case;
