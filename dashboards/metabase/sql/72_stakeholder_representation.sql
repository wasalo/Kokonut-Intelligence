-- Stakeholder representation: participation rates, accessibility, and minority views.
SELECT
  l.name AS location,
  sp.decision_id,
  sd.title AS decision_title,
  sp.party_id,
  p.name AS party_name,
  sp.status AS participation_status,
  sp.consent_checked,
  COALESCE(ar.accessibility_type, 'none') AS accessibility_request,
  COALESCE(mv.view_text, '') AS minority_view
FROM stakeholder_participation sp
JOIN party p ON p.id = sp.party_id
LEFT JOIN stakeholder_decision sd ON sd.id = sp.decision_id
LEFT JOIN stakeholder_accessibility_request ar ON ar.participation_id = sp.id
LEFT JOIN stakeholder_minority_view mv ON mv.participation_id = sp.id
LEFT JOIN party_identifier loc ON loc.party_id = sp.party_id AND loc.identifier_type = 'location_id'
LEFT JOIN location l ON l.id = loc.identifier_value::uuid
ORDER BY sp.created_at DESC;
