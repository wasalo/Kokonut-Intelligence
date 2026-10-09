-- Stakeholder engagement: plans, objectives, touchpoints, and commitment health.
SELECT
  l.name AS location,
  ep.plan_name,
  ep.stakeholder_party_id,
  p.name AS stakeholder_name,
  ep.status AS plan_status,
  (SELECT COUNT(*) FROM stakeholder_engagement_objective eo WHERE eo.plan_id = ep.id) AS objective_count,
  (SELECT COUNT(*) FROM stakeholder_commitment sc WHERE sc.plan_id = ep.id) AS commitment_count,
  (SELECT COUNT(*) FROM stakeholder_commitment sc WHERE sc.plan_id = ep.id AND sc.status = 'completed') AS commitments_completed,
  ep.created_at
FROM stakeholder_engagement_plan ep
JOIN party p ON p.id = ep.stakeholder_party_id
LEFT JOIN party_identifier loc ON loc.party_id = ep.stakeholder_party_id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
WHERE ep.status IN ('active', 'completed')
ORDER BY ep.created_at DESC;
