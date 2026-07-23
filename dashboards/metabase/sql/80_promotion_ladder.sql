-- Promotion ladder: data progression from sensor reading to verified metric to published credit.
SELECT
  l.name AS location,
  (SELECT COUNT(*) FROM sensor_reading sr WHERE sr.location_id = l.id) AS sensor_readings,
  (SELECT COUNT(*) FROM metric_value mv WHERE mv.location_id = l.id AND mv.verified = FALSE) AS draft_metrics,
  (SELECT COUNT(*) FROM metric_value mv WHERE mv.location_id = l.id AND mv.verified = TRUE) AS verified_metrics,
  (SELECT COUNT(*) FROM carbon_credit cc WHERE cc.location_id = l.id AND cc.status = 'published') AS published_credits,
  (SELECT COUNT(*) FROM retirement_certificate rc WHERE rc.location_id = l.id AND rc.status IN ('issued', 'verified', 'published')) AS retirement_certs
FROM location l
ORDER BY l.name;
