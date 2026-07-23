-- Climate impact: carbon balance, GHG emissions, tree carbon, and regenerative score.
SELECT
  l.name AS location,
  cis.reporting_year,
  cis.total_carbon_sequestered_tonnes,
  cis.total_ghg_emissions_tonnes,
  cis.net_carbon_balance_tonnes,
  cis.regenerative_score,
  cis.status,
  cis.created_at
FROM climate_impact_summary cis
JOIN location l ON l.id = cis.location_id
WHERE cis.status IN ('verified', 'published')
ORDER BY cis.reporting_year DESC, l.name;
