-- Stakeholder decision lineage: decisions, participants, trade-offs, evidence, outcomes.
SELECT
  l.name AS location,
  sd.id AS decision_id,
  sd.title,
  sd.description,
  sd.decision_type,
  sd.status AS decision_status,
  sd.created_by_party_id,
  cp.name AS created_by,
  (SELECT COUNT(*) FROM stakeholder_decision_participant sdp WHERE sdp.decision_id = sd.id) AS participant_count,
  (SELECT COUNT(*) FROM stakeholder_decision_tradeoff sdt WHERE sdt.decision_id = sd.id) AS tradeoff_count,
  (SELECT COUNT(*) FROM stakeholder_decision_evidence sde WHERE sde.decision_id = sd.id) AS evidence_count,
  sd.created_at,
  sd.completed_at
FROM stakeholder_decision sd
JOIN party cp ON cp.id = sd.created_by_party_id
LEFT JOIN party_identifier loc ON loc.party_id = sd.created_by_party_id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
ORDER BY sd.created_at DESC;
