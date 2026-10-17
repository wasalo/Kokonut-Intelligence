-- Keep location-level provider summaries idempotent. Refuse to select or
-- discard legacy duplicates; an operator must reconcile them before applying.

BEGIN;

DO $$
DECLARE
    v_duplicate_table TEXT;
BEGIN
    SELECT candidate.table_name
      INTO v_duplicate_table
      FROM (
          SELECT 'ncep_weather_summary'::TEXT AS table_name
           WHERE EXISTS (
               SELECT 1 FROM public.ncep_weather_summary
                WHERE plot_id IS NULL
                  AND source IS NOT NULL
                GROUP BY location_id, target_date, source
               HAVING COUNT(*) > 1
           )
          UNION ALL
          SELECT 'modis_lst_summary'::TEXT
           WHERE EXISTS (
               SELECT 1 FROM public.modis_lst_summary
                WHERE plot_id IS NULL
                  AND source IS NOT NULL
                GROUP BY location_id, target_date, source
               HAVING COUNT(*) > 1
           )
          UNION ALL
          SELECT 'smap_soil_moisture'::TEXT
           WHERE EXISTS (
               SELECT 1 FROM public.smap_soil_moisture
                WHERE plot_id IS NULL
                  AND source IS NOT NULL
                GROUP BY location_id, target_date, source
               HAVING COUNT(*) > 1
           )
          UNION ALL
          SELECT 'sentinel1_sar_summary'::TEXT
           WHERE EXISTS (
               SELECT 1 FROM public.sentinel1_sar_summary
                WHERE plot_id IS NULL
                  AND source IS NOT NULL
                GROUP BY location_id, target_date, source
               HAVING COUNT(*) > 1
           )
      ) AS candidate
     LIMIT 1;

    IF v_duplicate_table IS NOT NULL THEN
        RAISE EXCEPTION
            'Cannot add climate summary idempotency keys: duplicate location-level rows exist in %; reconcile them first',
            v_duplicate_table;
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ncep_weather_location_source_date
    ON public.ncep_weather_summary (location_id, target_date, source)
    WHERE plot_id IS NULL AND source IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_modis_lst_location_source_date
    ON public.modis_lst_summary (location_id, target_date, source)
    WHERE plot_id IS NULL AND source IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_smap_soil_moisture_location_source_date
    ON public.smap_soil_moisture (location_id, target_date, source)
    WHERE plot_id IS NULL AND source IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_sentinel1_sar_location_source_date
    ON public.sentinel1_sar_summary (location_id, target_date, source)
    WHERE plot_id IS NULL AND source IS NOT NULL;

COMMENT ON INDEX public.uq_ncep_weather_location_source_date IS
    'One location-level ERA5 summary per source and as-of date.';
COMMENT ON INDEX public.uq_modis_lst_location_source_date IS
    'One location-level MODIS LST summary per source and as-of date.';
COMMENT ON INDEX public.uq_smap_soil_moisture_location_source_date IS
    'One location-level SMAP summary per source and as-of date.';
COMMENT ON INDEX public.uq_sentinel1_sar_location_source_date IS
    'One location-level Sentinel-1 summary per source and as-of date.';

COMMIT;
