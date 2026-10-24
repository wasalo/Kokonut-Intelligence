-- The climate ingestion compatibility path writes one location-level
-- latitude proxy while preserving any optional plot-level WorldClim records.
-- Refuse to choose or delete legacy duplicates automatically.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.worldclim_climate
        WHERE plot_id IS NULL
        GROUP BY location_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Cannot add location-level WorldClim baseline key: duplicate rows need reviewed reconciliation';
    END IF;
END;
$$;

CREATE UNIQUE INDEX uq_worldclim_climate_location_baseline
    ON public.worldclim_climate (location_id)
    WHERE plot_id IS NULL;

-- Prefer plot-specific WorldClim rows, then fall back to the location-level
-- proxy produced by climate_data. LATERAL keeps the feature view one-row-per
-- plot/date when both kinds of baseline exist.
CREATE OR REPLACE VIEW public.v_dsm_feature_set AS
SELECT
    rsl.location_id,
    l.name AS location_name,
    rsl.plot_id,
    rsl.target_date,
    rsl.ndvi_median,
    rsl.savi_median,
    rsl.satvi_median,
    rsl.bsi_median,
    rsl.nbr2_median,
    rsl.ndti_median,
    rsl.lswi_median,
    rsl.tc_brightness_median,
    rsl.tc_greenness_median,
    rsl.tc_wetness_median,
    rsl.ndvi_range,
    wts.soil_moisture_mean,
    wts.mean_temp_mean,
    wts.precipitation_sum,
    wts.potential_et_mean,
    mts.lst_day_mean,
    mts.lst_night_mean,
    sts.soil_moisture_mean AS smap_moisture_mean,
    s1s.vh_median,
    s1s.vv_median,
    wc.bio1_mean_annual_temp,
    wc.bio16_precip_wettest_quarter,
    wc.bio17_precip_driest_quarter
FROM public.rs_time_series_feature rsl
JOIN public.location l ON rsl.location_id = l.id
LEFT JOIN public.weather_time_series_feature wts
    ON wts.location_id = rsl.location_id
   AND wts.target_date = rsl.target_date
   AND wts.reducer_type = 'seasonal_mean'
   AND wts.season IS NULL
LEFT JOIN public.modis_lst_time_series mts
    ON mts.location_id = rsl.location_id
   AND mts.target_date = rsl.target_date
   AND mts.reducer_type = 'seasonal_mean'
   AND mts.season IS NULL
LEFT JOIN public.smap_moisture_time_series sts
    ON sts.location_id = rsl.location_id
   AND sts.target_date = rsl.target_date
   AND sts.reducer_type = 'seasonal_mean'
   AND sts.season IS NULL
LEFT JOIN public.sentinel1_time_series s1s
    ON s1s.location_id = rsl.location_id
   AND s1s.target_date = rsl.target_date
   AND s1s.reducer_type = 'seasonal_median'
   AND s1s.season IS NULL
LEFT JOIN LATERAL (
    SELECT baseline.bio1_mean_annual_temp,
           baseline.bio16_precip_wettest_quarter,
           baseline.bio17_precip_driest_quarter
    FROM public.worldclim_climate baseline
    WHERE baseline.location_id = rsl.location_id
      AND (baseline.plot_id = rsl.plot_id OR baseline.plot_id IS NULL)
    ORDER BY (baseline.plot_id = rsl.plot_id) DESC NULLS LAST,
             baseline.updated_at DESC,
             baseline.id
    LIMIT 1
) wc ON TRUE
WHERE rsl.reducer_type = 'simple_median'
  AND l.status IN ('active', 'verified', 'published');
