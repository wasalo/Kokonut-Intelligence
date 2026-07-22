-- Organic transition progress: transition milestones, timeline, and compliance trajectory.
SELECT
  l.name AS location,
  otr.plan_name,
  otr.transition_start_date,
  otr.target_certification_date,
  otr.current_phase,
  otr.overall_progress_pct,
  otr.prohibited_substance_free_days,
  otr required_substance_free_days,
  otr.status AS plan_status,
  otr.created_at
FROM organic_transition_plan otr
JOIN location l ON l.id = otr.location_id
WHERE otr.status IN ('active', 'completed')
ORDER BY otr.created_at DESC;
