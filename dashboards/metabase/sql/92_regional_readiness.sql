-- Regional readiness: dimension scores, benchmarks, and readiness assessment.
SELECT
  l.name AS location,
  rra.title AS assessment_title,
  rra.period_start,
  rra.period_end,
  rds.dimension_key,
  rd.dimension_name,
  rds.score AS dimension_score,
  rds.weight,
  rra.overall_score,
  rra.status AS assessment_status
FROM regional_readiness_assessment rra
JOIN regional_readiness_dimension_score rds ON rds.assessment_id = rra.id
JOIN readiness_dimension rd ON rd.dimension_key = rds.dimension_key
LEFT JOIN location l ON l.id = rra.location_id
WHERE rra.status = 'active'
ORDER BY rra.created_at DESC, rds.score DESC;
