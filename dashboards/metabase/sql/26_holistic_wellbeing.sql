-- Holistic well-being dashboard: public-safe cultural context and well-being metrics.
SELECT
  l.name AS location,
  w.metric_key,
  w.metric_name,
  w.stakeholder_group,
  w.language,
  w.score_value,
  w.count_value,
  w.evidence_maturity,
  w.evidence_maturity_label,
  w.public_summary,
  w.observation_date
FROM v_public_wellbeing_metric_summary w
JOIN location l ON l.id = w.location_id
UNION ALL
SELECT
  l.name AS location,
  'cultural_context' AS metric_key,
  c.practice_name AS metric_name,
  c.stakeholder_group,
  c.language,
  NULL::numeric AS score_value,
  1 AS count_value,
  c.evidence_maturity,
  c.evidence_maturity_label,
  c.public_summary,
  NULL::date AS observation_date
FROM v_public_cultural_context_summary c
JOIN location l ON l.id = c.location_id
ORDER BY location, metric_key, observation_date DESC NULLS LAST;
