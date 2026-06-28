-- Perpetual value stress dashboard: downside runway, NOI, and solvency signals.
SELECT
  COALESCE(l.name, 'Network') AS source_location,
  s.scenario_name,
  s.scenario_date,
  s.stress_type,
  s.revenue_change_pct,
  s.cost_change_pct,
  s.grant_delay_months,
  s.yield_change_pct,
  s.baseline_runway_months,
  s.downside_runway_months,
  s.baseline_noi_usd,
  s.downside_noi_usd,
  s.solvency_status,
  s.mitigation_actions,
  s.evidence_maturity,
  s.evidence_maturity_label,
  s.public_summary
FROM v_public_perpetual_value_stress_test s
LEFT JOIN location l ON l.id = s.location_id
ORDER BY s.scenario_date DESC, s.stress_type;
