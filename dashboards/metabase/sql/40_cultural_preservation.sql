-- Cultural preservation dashboard: public-safe cultural, language, consent, and local-review evidence.
SELECT
  l.name AS location,
  c.plan_date,
  c.cultural_element,
  c.preservation_type,
  c.local_language,
  c.digital_integration_strategy,
  c.consent_protocol,
  c.local_reviewer_role,
  c.implementation_status,
  c.evidence_maturity,
  c.evidence_maturity_label,
  c.public_summary
FROM v_public_cultural_preservation_summary c
JOIN location l ON l.id = c.location_id
ORDER BY c.plan_date DESC, c.cultural_element;
