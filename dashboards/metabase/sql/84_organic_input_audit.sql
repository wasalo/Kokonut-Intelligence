-- Organic input audit: input compliance, prohibited substances, and harvest segregation.
SELECT
  l.name AS location,
  oia.product_name,
  oia.ingredient_list,
  oia.organic_status,
  oia.is_prohibited,
  oia.certifier,
  oia.certification_number,
  oia.audit_date,
  oia.compliance_notes,
  hsr.batch_id,
  hsr.segregation_type,
  hsr.compliance_status
FROM organic_input_audit oia
JOIN location l ON l.id = oia.location_id
LEFT JOIN harvest_segregation_record hsr ON hsr.location_id = oia.location_id
WHERE oia.status = 'active'
ORDER BY oia.is_prohibited DESC, oia.audit_date DESC;
