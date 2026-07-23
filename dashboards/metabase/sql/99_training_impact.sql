-- Training impact: training programs, attendance, completion, and skill improvement.
SELECT
  l.name AS location,
  te.event_name,
  te.event_type,
  te.target_audience,
  te.planned_date,
  te.actual_date,
  te.attendee_count,
  te.completion_rate_pct,
  te.avg_assessment_score,
  te.status AS event_status
FROM training_event te
JOIN location l ON l.id = te.location_id
WHERE te.status IN ('completed', 'verified')
ORDER BY te.actual_date DESC;
