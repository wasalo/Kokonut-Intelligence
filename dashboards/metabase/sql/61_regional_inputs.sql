-- LAC Regional Inputs dashboard: public-safe regional input availability for bio-organic fertilizer production.
SELECT
  r.region_scope,
  r.input_name,
  r.input_category,
  r.country,
  r.subregion,
  r.seasonality,
  r.cautions,
  r.quality_considerations,
  r.typical_suppliers,
  r.evidence_maturity,
  r.evidence_maturity_label,
  r.public_summary
FROM v_public_bio_regional_input_summary r
ORDER BY r.region_scope, r.input_name;
