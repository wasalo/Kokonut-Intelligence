-- Stakeholder cockpit: consolidated stakeholder view with salience, trust, and engagement.
SELECT
  l.name AS location,
  p.id AS party_id,
  p.name AS party_name,
  p.party_type,
  COALESCE(sa.legitimacy_score, 0) AS legitimacy,
  COALESCE(sa.harm_exposure, 0) AS harm_exposure,
  COALESCE(sa.power_score, 0) AS power,
  COALESCE(si.interest_description, '') AS interest,
  (SELECT COUNT(*) FROM party_trust_evidence pte WHERE pte.party_id = p.id AND pte.status = 'active') AS trust_evidence_count,
  (SELECT COUNT(*) FROM stakeholder_engagement_plan ep WHERE ep.stakeholder_party_id = p.id AND ep.status = 'active') AS active_plans
FROM party p
LEFT JOIN stakeholder_salience_assessment sa ON sa.party_id = p.id AND sa.status = 'active'
LEFT JOIN stakeholder_interest si ON si.party_id = p.id AND si.status = 'active'
LEFT JOIN party_identifier loc ON loc.party_id = p.id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
WHERE p.status = 'active'
ORDER BY COALESCE(sa.legitimacy_score, 0) DESC;
