-- Stakeholder trust: trust profiles, evidence, dispute performance, and risk indicators.
SELECT
  l.name AS location,
  p.id AS party_id,
  p.name AS party_name,
  p.party_type,
  COALESCE(tp.trust_score, 0) AS trust_score,
  COALESCE(tp.evidence_count, 0) AS trust_evidence_count,
  COALESCE(tp.last_updated, p.updated_at) AS last_trust_update,
  COALESCE(rri.risk_level, 'none') AS risk_level,
  COALESCE(rri.risk_description, '') AS risk_description
FROM party p
LEFT JOIN LATERAL (
  SELECT
    AVG(te.confidence) AS trust_score,
    COUNT(*) AS evidence_count,
    MAX(te.created_at) AS last_updated
  FROM party_trust_evidence te
  WHERE te.party_id = p.id AND te.status = 'active'
) tp ON true
LEFT JOIN LATERAL (
  SELECT rri2.risk_level, rri2.risk_description
  FROM relationship_risk_indicator rri2
  WHERE rri2.from_party_id = p.id OR rri2.to_party_id = p.id
  ORDER BY rri2.created_at DESC LIMIT 1
) rri ON true
LEFT JOIN party_identifier loc ON loc.party_id = p.id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
WHERE p.status = 'active'
ORDER BY COALESCE(tp.trust_score, 0) DESC;
