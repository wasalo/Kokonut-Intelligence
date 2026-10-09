-- PESTEL assessment: political, economic, social, technological, environmental, legal factors.
SELECT
  l.name AS location,
  pa.title AS analysis_title,
  pa.period_start,
  pa.period_end,
  pf.category,
  pf.factor_type,
  pf.title AS factor_title,
  pf.impact,
  pf.likelihood,
  pf.impact * pf.likelihood AS risk_score
FROM pestel_analysis pa
JOIN pestel_factor pf ON pf.analysis_id = pa.id
LEFT JOIN location l ON l.id = pa.location_id
WHERE pa.status = 'active'
ORDER BY pa.created_at DESC, pf.category, risk_score DESC;
