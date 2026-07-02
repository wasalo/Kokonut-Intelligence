-- Bio Recipe Library dashboard: public-safe bio-organic fertilizer recipes.
SELECT
  l.name AS location,
  r.recipe_name,
  r.recipe_type,
  r.recipe_category,
  r.fermentation_days,
  r.target_c_n_ratio,
  r.target_moisture_pct,
  r.target_temperature_c,
  r.target_ph,
  r.dilution_ratio,
  r.application_method,
  r.quality_warnings,
  r.evidence_maturity,
  r.evidence_maturity_label,
  r.public_summary
FROM v_public_bio_recipe_library_summary r
LEFT JOIN location l ON l.id = r.location_id
ORDER BY r.recipe_type, r.recipe_name;
