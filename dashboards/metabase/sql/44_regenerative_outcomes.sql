-- Regenerative outcomes dashboard: concise ecological and social impact summary.
SELECT
  l.name AS location,
  r.period_start,
  r.period_end,
  r.summary_name,
  r.hectares_restored,
  r.baseline_species_count,
  r.latest_species_count,
  r.species_diversity_delta,
  r.baseline_soil_carbon_t_ha,
  r.latest_soil_carbon_t_ha,
  r.soil_carbon_delta_t_ha,
  r.trees_planted_count,
  r.trees_surviving_count,
  r.tree_survival_rate_pct,
  r.regenerative_score,
  r.jobs_or_roles_supported_count,
  r.training_hours,
  r.beneficiary_count,
  r.evidence_confidence,
  r.evidence_maturity,
  r.evidence_maturity_label,
  r.public_summary
FROM v_public_regenerative_outcome_summary r
JOIN location l ON l.id = r.location_id
ORDER BY r.period_end DESC, r.summary_name;
