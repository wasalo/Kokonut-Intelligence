-- Keep the crop-cycle label in a revenue-stream row within that row's location.

BEGIN;

CREATE OR REPLACE VIEW v_public_revenue_streams AS
SELECT
    rsc.id,
    rsc.location_id,
    l.name AS location_name,
    rsc.crop_cycle_id,
    cc.cycle_name,
    rsc.period_start,
    rsc.period_end,
    rsc.stream_name,
    rsc.stream_category,
    rsc.gross_revenue,
    rsc.direct_costs,
    rsc.allocated_costs,
    rsc.net_contribution,
    rsc.contribution_pct,
    rsc.notes,
    rsc.status
FROM revenue_stream_contribution rsc
JOIN location l ON l.id = rsc.location_id
LEFT JOIN crop_cycle cc
    ON cc.id = rsc.crop_cycle_id
   AND cc.location_id = rsc.location_id
WHERE l.status = 'active'
  AND rsc.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

COMMIT;
