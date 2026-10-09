-- Stakeholder outcomes: verified outcomes linked to capabilities and value streams.
SELECT
  l.name AS location,
  so.id AS outcome_id,
  so.title,
  so.description,
  so.outcome_type,
  so.status,
  so.severity,
  so.location_id,
  so.created_at,
  so.verified_at
FROM stakeholder_outcome so
LEFT JOIN party_identifier loc ON loc.party_id = so.stakeholder_party_id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
WHERE so.status IN ('verified', 'published')
ORDER BY so.created_at DESC;
