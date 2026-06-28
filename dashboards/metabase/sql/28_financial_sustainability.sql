-- Financial sustainability dashboard: public-safe grant dependency, reinvestment, public-goods allocation, and runway.
SELECT
  l.name AS location,
  f.plan_name,
  f.farm_model,
  f.sustainability_status,
  f.grant_dependency_pct,
  f.reinvestment_pct,
  f.public_goods_allocation_pct,
  f.break_even_month,
  f.runway_months,
  f.projected_annual_revenue_usd,
  f.projected_annual_operating_cost_usd,
  f.projected_annual_noi_usd,
  f.evidence_maturity,
  f.evidence_maturity_label,
  f.public_summary
FROM v_public_financial_sustainability_summary f
JOIN location l ON l.id = f.location_id
ORDER BY f.plan_period_start DESC, f.plan_name;
