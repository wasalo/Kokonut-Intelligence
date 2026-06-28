-- Foundational well-being dashboard: public-safe happiness, peace, safety, and basic-needs signals.
SELECT
  l.name AS location,
  f.observation_date,
  f.wellbeing_domain,
  f.stakeholder_group,
  f.score_value,
  f.count_value,
  f.evidence_maturity,
  f.evidence_maturity_label,
  f.public_summary
FROM v_public_foundational_wellbeing_summary f
JOIN location l ON l.id = f.location_id
ORDER BY f.observation_date DESC, f.wellbeing_domain;
