-- Publics and market landscape: stakeholder publics, market segments, and influence matrix.
SELECT
  l.name AS location,
  sp.public_type,
  sp.name AS public_name,
  sp.influence_score,
  sp.interest_score,
  sp.stance,
  ms.segment_type,
  ms.name AS segment_name,
  ms.size_estimate
FROM stakeholder_public sp
LEFT JOIN location l ON l.id = sp.location_id
LEFT JOIN market_segment ms ON ms.location_id = sp.location_id AND ms.status = 'active'
WHERE sp.status = 'active'
ORDER BY sp.influence_score DESC NULLS LAST;
