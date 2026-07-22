-- Technology roadmap: areas, drivers, alternatives, requirements, and maturity.
SELECT
  tr.id AS roadmap_id,
  tr.roadmap_name,
  ta.area_name,
  td.driver_name,
  td.priority AS driver_priority,
  ta.alternative_name,
  ta.maturity_level,
  ta.readiness_score,
  ta.estimated_cost_usd,
  ta.review_status
FROM technology_roadmap tr
JOIN technology_area ta ON ta.roadmap_id = tr.id
JOIN technology_driver td ON td.area_id = ta.id
LEFT JOIN technology_alternative alt ON alt.driver_id = td.id
WHERE tr.status = 'active'
ORDER BY tr.roadmap_name, ta.area_name, td.priority;
