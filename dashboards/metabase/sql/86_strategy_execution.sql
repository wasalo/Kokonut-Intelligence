-- Strategy execution: objectives, initiatives, investment cases, and coherence.
SELECT
  sp.id AS plan_id,
  sp.plan_name,
  so.id AS objective_id,
  so.title AS objective_title,
  so.perspective,
  so.target_value,
  so.current_value,
  CASE WHEN so.target_value > 0
    THEN ROUND((so.current_value / so.target_value * 100)::numeric, 1)
    ELSE 0
  END AS progress_pct,
  si.title AS initiative_title,
  si.status AS initiative_status,
  si.priority
FROM strategy_plan sp
JOIN strategy_objective so ON so.plan_id = sp.id
LEFT JOIN strategy_initiative si ON si.objective_id = so.id
WHERE sp.status = 'active' AND so.status = 'active'
ORDER BY so.perspective, so.title;
