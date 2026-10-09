-- Governance coordination health: circles, roles, proposals, tensions, and link health.
SELECT
  gc.id AS circle_id,
  gc.circle_name,
  gc.circle_type,
  gc.status AS circle_status,
  (SELECT COUNT(*) FROM governance_role gr WHERE gr.circle_id = gc.id) AS role_count,
  (SELECT COUNT(*) FROM governance_proposal gp WHERE gp.circle_id = gc.id AND gp.status = 'open') AS open_proposals,
  (SELECT COUNT(*) FROM governance_tension gt WHERE gt.circle_id = gc.id AND gt.status = 'open') AS open_tensions,
  gc.created_at
FROM governance_circle gc
WHERE gc.status = 'active'
ORDER BY gc.circle_name;
