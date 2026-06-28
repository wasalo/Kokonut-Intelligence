-- Capital provider utility dashboard: public-safe funder/sponsor utility scenarios with limitations.
SELECT
  l.name AS location,
  u.scenario_name,
  u.provider_type,
  u.capital_amount_usd,
  u.expected_financial_return_usd,
  u.expected_public_goods_value_usd,
  u.expected_verification_outputs,
  u.expected_payback_months,
  u.utility_score,
  u.limitations,
  u.evidence_maturity,
  u.evidence_maturity_label,
  u.public_summary
FROM v_public_capital_provider_utility_summary u
JOIN location l ON l.id = u.location_id
ORDER BY u.utility_score DESC NULLS LAST, u.scenario_name;
