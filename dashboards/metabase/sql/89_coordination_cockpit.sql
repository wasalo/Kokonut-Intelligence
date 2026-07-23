-- Coordination cockpit: alliances, participants, objectives, contributions, and benefits.
SELECT
  ca.id AS alliance_id,
  ca.alliance_name,
  ca.alliance_type,
  ca.status AS alliance_status,
  (SELECT COUNT(*) FROM coordination_participant cp WHERE cp.alliance_id = ca.id) AS participant_count,
  (SELECT COUNT(*) FROM coordination_objective co WHERE co.alliance_id = ca.id) AS objective_count,
  (SELECT COUNT(*) FROM coordination_contribution cc WHERE cc.alliance_id = ca.id) AS contribution_count,
  ca.created_at,
  ca.next_review_date
FROM coordination_alliance ca
WHERE ca.status IN ('active', 'proposed')
ORDER BY ca.created_at DESC;
