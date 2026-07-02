-- Bio Quality & Distribution dashboard: public-safe quality test results and distribution tracking.
SELECT
  l.name AS location,
  q.test_date,
  q.test_type,
  q.parameter_name,
  q.measured_value,
  q.unit,
  q.target_min,
  q.target_max,
  q.pass_fail,
  q.lab_name,
  q.lab_accredited,
  q.evidence_maturity,
  q.evidence_maturity_label,
  q.public_summary
FROM v_public_bio_factory_quality_test_summary q
LEFT JOIN location l ON l.id = q.location_id
ORDER BY q.test_date DESC, q.parameter_name;
