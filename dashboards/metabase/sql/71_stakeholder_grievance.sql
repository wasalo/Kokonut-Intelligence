-- Stakeholder grievance: cases, investigations, remedies, and resolution status.
SELECT
  l.name AS location,
  gc.case_id,
  gc.complaint_type,
  gc.description,
  gc.severity,
  gc.status AS case_status,
  gc.owner_party_id,
  op.name AS owner_name,
  gc.created_at,
  gc.resolved_at,
  CASE WHEN gc.resolved_at IS NOT NULL
    THEN EXTRACT(EPOCH FROM (gc.resolved_at - gc.created_at)) / 86400
    ELSE NULL
  END AS days_to_resolve
FROM stakeholder_grievance_case gc
JOIN party op ON op.id = gc.owner_party_id
LEFT JOIN party_identifier loc ON loc.party_id = gc.complainant_party_id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
ORDER BY gc.created_at DESC;
