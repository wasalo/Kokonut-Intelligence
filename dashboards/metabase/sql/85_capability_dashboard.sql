-- Capability dashboard: capability maturity, process/service coverage, and gaps.
SELECT
  bc.id AS capability_id,
  bc.name AS capability_name,
  bc.description,
  bc.guild,
  COALESCE(cma.maturity_level, 'unassessed') AS maturity_level,
  COALESCE(cma.maturity_score, 0) AS maturity_score,
  (SELECT COUNT(*) FROM capability_process_map cpm WHERE cpm.capability_id = bc.id) AS mapped_processes,
  (SELECT COUNT(*) FROM capability_service_map csm WHERE csm.capability_id = bc.id) AS mapped_services
FROM business_capability bc
LEFT JOIN capability_maturity_assessment cma ON cma.capability_id = bc.id AND cma.status = 'active'
WHERE bc.status = 'active'
ORDER BY COALESCE(cma.maturity_score, 0) DESC;
