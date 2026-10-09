-- Stakeholder landscape: party types, salience, and relationship mapping.
SELECT
  l.name AS location,
  p.id AS party_id,
  p.party_type,
  p.name AS party_name,
  COALESCE(pi.identifier_value, '') AS identifier,
  COALESCE(sa.legitimacy_score, 0) AS legitimacy,
  COALESCE(sa.harm_exposure, 0) AS harm_exposure,
  COALESCE(sa.power_score, 0) AS power,
  sa.rationale
FROM party p
JOIN party_identifier pi ON pi.party_id = p.id AND pi.status = 'active'
LEFT JOIN stakeholder_salience_assessment sa ON sa.party_id = p.id AND sa.status = 'active'
LEFT JOIN party_identifier loc ON loc.party_id = p.id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
WHERE p.status = 'active'
ORDER BY COALESCE(sa.legitimacy_score, 0) DESC;
