-- Scaling economics dashboard: launch unit economics and network targets.
SELECT
  COALESCE(l.name, 'Network') AS source_location,
  e.economics_name,
  e.target_region,
  e.farm_model,
  e.planned_farm_count,
  e.planned_hectares,
  e.expected_beneficiary_count,
  e.total_launch_cost_usd,
  e.cost_per_farm_usd,
  e.cost_per_hectare_usd,
  e.cost_per_beneficiary_usd,
  e.projected_annual_revenue_usd,
  e.projected_annual_noi_usd,
  e.projected_roi_pct,
  e.payback_months,
  e.launch_timeline_months,
  e.evidence_confidence,
  e.evidence_maturity,
  e.evidence_maturity_label,
  e.public_summary
FROM v_public_farm_launch_unit_economics e
LEFT JOIN location l ON l.id = e.location_id
UNION ALL
SELECT
  'Network' AS source_location,
  t.target_name AS economics_name,
  t.target_region,
  t.farm_model,
  t.target_farm_count AS planned_farm_count,
  t.target_hectares AS planned_hectares,
  t.target_beneficiary_count AS expected_beneficiary_count,
  t.capital_required_usd AS total_launch_cost_usd,
  t.capital_required_per_farm_usd AS cost_per_farm_usd,
  CASE WHEN t.target_hectares > 0 THEN ROUND(t.capital_required_usd / t.target_hectares, 2) ELSE NULL END AS cost_per_hectare_usd,
  CASE WHEN t.target_beneficiary_count > 0 THEN ROUND(t.capital_required_usd / t.target_beneficiary_count, 2) ELSE NULL END AS cost_per_beneficiary_usd,
  NULL AS projected_annual_revenue_usd,
  NULL AS projected_annual_noi_usd,
  NULL AS projected_roi_pct,
  NULL AS payback_months,
  NULL AS launch_timeline_months,
  NULL AS evidence_confidence,
  t.evidence_maturity,
  t.evidence_maturity_label,
  t.public_summary
FROM v_public_network_scaling_target t
ORDER BY target_region, economics_name;
