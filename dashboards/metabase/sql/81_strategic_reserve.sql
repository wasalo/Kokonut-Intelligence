-- Strategic reserve: reserve health, adequacy, trigger status, and drawdown headroom.
SELECT
  l.name AS location,
  sr.reserve_code,
  sr.reserve_name,
  sr.reserve_type,
  sr.current_quantity,
  sr.adequacy_threshold,
  sr.breach_threshold,
  CASE
    WHEN sr.current_quantity >= sr.adequacy_threshold THEN 'adequate'
    WHEN sr.current_quantity >= sr.breach_threshold THEN 'warning'
    ELSE 'breach'
  END AS reserve_status,
  sr.current_quantity - sr.breach_threshold AS drawdown_headroom,
  sr.trigger_metric_key,
  sr.last_evaluated_at
FROM strategic_reserve sr
JOIN location l ON l.id = sr.location_id
WHERE sr.status = 'active'
ORDER BY sr.reserve_code;
