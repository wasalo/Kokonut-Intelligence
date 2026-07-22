-- Stakeholder ecosystem: relationships, risk indicators, and recommendations.
SELECT
  l.name AS location,
  pr.from_party_id,
  pf.name AS from_party,
  pr.to_party_id,
  pt.name AS to_party,
  pr.relationship_type,
  pr.status AS relationship_status,
  COALESCE(rri.risk_level, 'none') AS risk_level,
  COALESCE(rri.risk_description, '') AS risk_description
FROM party_relationship pr
JOIN party pf ON pf.id = pr.from_party_id
JOIN party pt ON pt.id = pr.to_party_id
LEFT JOIN relationship_risk_indicator rri ON rri.relationship_id = pr.id AND rri.status IN ('open', 'monitoring')
LEFT JOIN party_identifier loc ON loc.party_id = pr.from_party_id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
WHERE pr.status = 'active'
ORDER BY rri.risk_level DESC NULLS LAST;
