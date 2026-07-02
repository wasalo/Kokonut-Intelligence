-- Bio Input Provenance dashboard: public-safe ingredient sourcing with LAC regional focus and quality warnings.
SELECT
  l.name AS location,
  p.input_name,
  p.input_category,
  p.supplier_name,
  p.supplier_verified,
  p.organic_certified,
  p.origin_country,
  p.origin_region,
  p.input_kg,
  p.nutrient_n_pct,
  p.nutrient_p_pct,
  p.nutrient_k_pct,
  p.quality_warnings,
  p.evidence_maturity,
  p.evidence_maturity_label,
  p.public_summary
FROM v_public_bio_input_provenance_summary p
LEFT JOIN location l ON l.id = p.location_id
ORDER BY p.input_category, p.input_name;
