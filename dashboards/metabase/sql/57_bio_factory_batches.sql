-- Bio Factory Batches dashboard: public-safe bio-organic fertilizer production batches.
SELECT
  l.name AS location,
  b.batch_name,
  b.batch_type,
  b.production_method,
  b.production_start_date,
  b.production_end_date,
  b.input_kg_total,
  b.output_kg_total,
  b.output_liters_total,
  b.batch_yield_pct,
  b.moisture_pct,
  b.temperature_c,
  b.ph_level,
  b.microbial_strain,
  b.evidence_maturity,
  b.evidence_maturity_label,
  b.public_summary
FROM v_public_bio_factory_batch_summary b
LEFT JOIN location l ON l.id = b.location_id
ORDER BY b.production_start_date DESC, b.batch_name;
