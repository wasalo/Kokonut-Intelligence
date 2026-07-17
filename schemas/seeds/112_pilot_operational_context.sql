-- ============================================================
-- 112_pilot_operational_context.sql
-- Reconcile legacy pilot harvest context to canonical crop cycles.
-- ============================================================

UPDATE harvest_event h
SET plot_id = cc.plot_id,
    location_id = cc.location_id,
    notes = concat_ws('; ', h.notes, 'Pilot context reconciled to crop_cycle')
FROM crop_cycle cc
WHERE cc.id = h.crop_cycle_id
  AND (h.location_id <> cc.location_id OR h.plot_id <> cc.plot_id)
  AND h.source_system = 'pilot_seed';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM harvest_event h
        JOIN crop_cycle cc ON cc.id = h.crop_cycle_id
        WHERE h.location_id <> cc.location_id OR h.plot_id <> cc.plot_id
    ) THEN
        RAISE EXCEPTION 'pilot seed left harvest_event context mismatches';
    END IF;
END;
$$;
