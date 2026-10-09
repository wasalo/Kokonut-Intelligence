-- Value stream formal: stream definitions, stages, observations, and performance metrics.
SELECT
  vsd.id AS stream_id,
  vsd.stream_name,
  vsd.description,
  vsd.status AS stream_status,
  vss.id AS stage_id,
  vss.stage_name,
  vss.stage_order,
  vso.lead_time_hours,
  vso.first_time_through_yield_pct,
  vso.created_at AS observed_at
FROM value_stream_definition vsd
JOIN value_stream_stage vss ON vss.stream_id = vsd.id
LEFT JOIN value_stream_stage_observation vso ON vso.stage_id = vss.id
WHERE vsd.status = 'active'
ORDER BY vsd.stream_name, vss.stage_order;
