-- Capital efficiency dashboard: public-safe scenario and regenerative practice efficiency signals.
SELECT
  l.name AS location,
  c.scenario_name,
  c.scenario_type,
  c.period_start,
  c.period_end,
  c.capital_deployed_usd,
  c.gross_output_value_usd,
  c.net_output_value_usd,
  c.public_goods_value_usd,
  c.capital_leverage_ratio,
  r.practice_type,
  r.cost_savings_pct,
  r.payback_months,
  c.evidence_maturity,
  c.evidence_maturity_label,
  c.public_summary
FROM v_public_capital_efficiency_summary c
JOIN location l ON l.id = c.location_id
LEFT JOIN v_public_regenerative_efficiency_summary r ON r.location_id = c.location_id
ORDER BY c.period_start DESC, c.scenario_name, r.observation_date DESC;
