-- Move waste, composting, and recycling aggregates behind exact-grant reads.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_waste_summary_reader'
    ) THEN
        CREATE ROLE kokonut_waste_summary_reader;
    END IF;
END;
$$;

ALTER ROLE kokonut_waste_summary_reader
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_waste_summary_reader;
GRANT SELECT (
    location_id, waste_type, disposal_method, quantity_unit, quantity_kg,
    record_date, status
) ON TABLE public.waste_stream TO kokonut_waste_summary_reader;
GRANT SELECT (
    id, location_id, feedstock_type, compost_method, feedstock_kg, metadata,
    finished_volume_kg, duration_days, temperature_c, moisture_pct,
    quality_grade, compost_date, status
) ON TABLE public.composting_record TO kokonut_waste_summary_reader;
GRANT SELECT (
    location_id, material_type, quantity_kg, record_date, status
) ON TABLE public.recycling_log TO kokonut_waste_summary_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_waste_summary_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_waste_summary_reader;

DO $$
DECLARE
    relation_id REGCLASS;
    role_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH relation_id IN ARRAY ARRAY[
        'public.waste_stream'::REGCLASS,
        'public.composting_record'::REGCLASS,
        'public.recycling_log'::REGCLASS
    ] LOOP
        FOREACH role_name IN ARRAY ARRAY[
            'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'
        ] LOOP
            IF role_name = 'PUBLIC'
               OR EXISTS (
                   SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
               ) THEN
                EXECUTE pg_catalog.format(
                    'REVOKE SELECT ON TABLE %s FROM %s', relation_id,
                    CASE WHEN role_name = 'PUBLIC'
                         THEN 'PUBLIC'
                         ELSE pg_catalog.quote_ident(role_name)
                    END
                );
                FOR column_name IN
                    SELECT attribute.attname
                      FROM pg_catalog.pg_attribute AS attribute
                     WHERE attribute.attrelid = relation_id
                       AND attribute.attnum > 0
                       AND NOT attribute.attisdropped
                LOOP
                    EXECUTE pg_catalog.format(
                        'REVOKE SELECT (%1$I) ON TABLE %2$s FROM %3$s',
                        column_name,
                        relation_id,
                        CASE WHEN role_name = 'PUBLIC'
                             THEN 'PUBLIC'
                             ELSE pg_catalog.quote_ident(role_name)
                        END
                    );
                END LOOP;
            END IF;
        END LOOP;
    END LOOP;
END;
$$;

DO $$
DECLARE
    view_name TEXT;
    role_name TEXT;
BEGIN
    FOREACH view_name IN ARRAY ARRAY[
        'v_waste_summary', 'v_composting_efficiency'
    ] LOOP
        IF pg_catalog.to_regclass('public.' || view_name) IS NOT NULL THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.%I FROM PUBLIC', view_name
            );
            FOREACH role_name IN ARRAY ARRAY[
                'kokonut_runtime', 'kokonut_directus_runtime'
            ] LOOP
                IF EXISTS (
                    SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
                ) THEN
                    EXECUTE pg_catalog.format(
                        'REVOKE ALL ON TABLE public.%I FROM %I',
                        view_name, role_name
                    );
                END IF;
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.summarize_location_waste_operations(
    requested_location_id UUID,
    requested_days INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_days IS NULL
       OR requested_days < 1
       OR requested_days > 3650 THEN
        RAISE EXCEPTION 'Waste summary requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'waste_management', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Waste summary requires an exact location read grant'
            USING ERRCODE = '42501';
    END IF;

    WITH waste_groups AS (
        SELECT waste.waste_type, waste.disposal_method, waste.quantity_unit,
               pg_catalog.count(*)::BIGINT AS record_count,
               pg_catalog.sum(waste.quantity_kg)::NUMERIC AS total_quantity,
               pg_catalog.min(waste.record_date) AS first_date,
               pg_catalog.max(waste.record_date) AS last_date
          FROM public.waste_stream AS waste
         WHERE waste.location_id = requested_location_id
           AND waste.status = 'verified'
         GROUP BY waste.waste_type, waste.disposal_method, waste.quantity_unit
    ), waste_period_type AS (
        SELECT waste.waste_type,
               pg_catalog.sum(waste.quantity_kg)::NUMERIC AS total_kg,
               pg_catalog.count(*)::BIGINT AS record_count
          FROM public.waste_stream AS waste
         WHERE waste.location_id = requested_location_id
           AND waste.status = 'verified'
           AND waste.record_date >= CURRENT_DATE - (requested_days - 1)
         GROUP BY waste.waste_type
    ), waste_period_disposal AS (
        SELECT waste.disposal_method,
               pg_catalog.sum(waste.quantity_kg)::NUMERIC AS total_kg,
               pg_catalog.count(*)::BIGINT AS record_count
          FROM public.waste_stream AS waste
         WHERE waste.location_id = requested_location_id
           AND waste.status = 'verified'
           AND waste.record_date >= CURRENT_DATE - (requested_days - 1)
         GROUP BY waste.disposal_method
    ), waste_period_totals AS (
        SELECT COALESCE(pg_catalog.sum(waste.quantity_kg), 0)::NUMERIC AS total_kg,
               pg_catalog.count(*)::BIGINT AS record_count
          FROM public.waste_stream AS waste
         WHERE waste.location_id = requested_location_id
           AND waste.status = 'verified'
           AND waste.record_date >= CURRENT_DATE - (requested_days - 1)
    ), compost_groups AS (
        SELECT compost.feedstock_type, compost.compost_method,
               pg_catalog.count(*)::BIGINT AS record_count,
               pg_catalog.sum(compost.feedstock_kg)::NUMERIC AS feedstock_kg,
               COALESCE(pg_catalog.sum(compost.finished_volume_kg), 0)::NUMERIC AS total_output_kg,
               CASE
                   WHEN pg_catalog.sum(compost.feedstock_kg) > 0
                   THEN pg_catalog.round((
                       pg_catalog.sum(compost.finished_volume_kg)
                       / pg_catalog.sum(compost.feedstock_kg) * 100
                   )::NUMERIC, 1)
                   ELSE NULL
               END AS weighted_yield_pct,
               pg_catalog.round(pg_catalog.avg(
                   compost.finished_volume_kg
                   / NULLIF(compost.feedstock_kg, 0) * 100
               ) FILTER (
                   WHERE compost.finished_volume_kg IS NOT NULL
                     AND compost.feedstock_kg > 0
               )::NUMERIC, 1) AS mean_batch_yield_pct,
               pg_catalog.round(pg_catalog.avg(compost.duration_days) FILTER (
                   WHERE compost.finished_volume_kg IS NOT NULL
               )::NUMERIC, 1) AS mean_duration_days,
               pg_catalog.round(pg_catalog.avg(compost.temperature_c)::NUMERIC, 1)
                   AS mean_temperature_c,
               pg_catalog.round(pg_catalog.avg(compost.moisture_pct)::NUMERIC, 1)
                   AS mean_moisture_pct,
               pg_catalog.count(*) FILTER (
                   WHERE compost.quality_grade IS NOT NULL
               )::BIGINT AS graded_batches,
               pg_catalog.min(compost.compost_date) AS first_date,
               pg_catalog.max(compost.compost_date) AS last_date
          FROM public.composting_record AS compost
         WHERE compost.location_id = requested_location_id
           AND compost.status = 'verified'
         GROUP BY compost.feedstock_type, compost.compost_method
    ), compost_method_efficiency AS (
        SELECT compost.compost_method,
               pg_catalog.count(*)::BIGINT AS batches,
               pg_catalog.round(pg_catalog.avg(
                   compost.finished_volume_kg / NULLIF(compost.feedstock_kg, 0) * 100
               ) FILTER (
                   WHERE compost.finished_volume_kg IS NOT NULL
                     AND compost.feedstock_kg > 0
               )::NUMERIC, 1) AS avg_yield_pct,
               pg_catalog.avg(compost.feedstock_kg)::NUMERIC AS avg_feedstock_kg,
               pg_catalog.avg(compost.finished_volume_kg)::NUMERIC AS avg_output_kg,
               pg_catalog.avg(compost.duration_days)::NUMERIC AS avg_duration_days
          FROM public.composting_record AS compost
         WHERE compost.location_id = requested_location_id
           AND compost.status = 'verified'
           AND compost.finished_volume_kg IS NOT NULL
         GROUP BY compost.compost_method
    ), compost_totals AS (
        SELECT pg_catalog.count(*)::BIGINT AS total_batches,
               COALESCE(pg_catalog.sum(compost.feedstock_kg), 0)::NUMERIC AS total_feedstock_kg,
               COALESCE(pg_catalog.sum(compost.finished_volume_kg), 0)::NUMERIC AS total_output_kg
          FROM public.composting_record AS compost
         WHERE compost.location_id = requested_location_id
           AND compost.status = 'verified'
    ), compost_recent_quality AS (
        SELECT compost.id,
               CASE
                   WHEN pg_catalog.jsonb_typeof(compost.metadata -> 'ph') = 'number'
                   THEN (compost.metadata ->> 'ph')::NUMERIC
                   ELSE NULL
               END AS ph,
               compost.moisture_pct,
               compost.temperature_c,
               CASE
                   WHEN compost.feedstock_kg > 0
                    AND compost.finished_volume_kg IS NOT NULL
                   THEN pg_catalog.round((
                       compost.finished_volume_kg / compost.feedstock_kg * 100
                   )::NUMERIC, 1)
                   ELSE NULL
               END AS output_yield_pct,
               compost.compost_date AS recorded_at
          FROM public.composting_record AS compost
         WHERE compost.location_id = requested_location_id
           AND compost.status = 'verified'
         ORDER BY compost.compost_date DESC, compost.id DESC
         LIMIT 10
    ), recycling_groups AS (
        SELECT recycling.material_type,
               pg_catalog.count(*)::BIGINT AS record_count,
               pg_catalog.sum(recycling.quantity_kg)::NUMERIC AS quantity_kg,
               pg_catalog.min(recycling.record_date) AS first_date,
               pg_catalog.max(recycling.record_date) AS last_date
          FROM public.recycling_log AS recycling
         WHERE recycling.location_id = requested_location_id
           AND recycling.status = 'verified'
         GROUP BY recycling.material_type
    )
    SELECT pg_catalog.jsonb_build_object(
        'location_id', requested_location_id::TEXT,
        'waste_summary', (
            SELECT pg_catalog.jsonb_build_object(
                'period_days', requested_days,
                'total_waste_kg', totals.total_kg,
                'total_records', totals.record_count,
                'by_type', (
                    SELECT COALESCE(pg_catalog.jsonb_agg(
                        pg_catalog.jsonb_build_object(
                            'waste_type', grouped.waste_type,
                            'total_kg', grouped.total_kg,
                            'record_count', grouped.record_count
                        ) ORDER BY grouped.total_kg DESC, grouped.waste_type
                    ), '[]'::JSONB) FROM waste_period_type AS grouped
                ),
                'by_disposal_method', (
                    SELECT COALESCE(pg_catalog.jsonb_agg(
                        pg_catalog.jsonb_build_object(
                            'disposal_method', grouped.disposal_method,
                            'total_kg', grouped.total_kg,
                            'record_count', grouped.record_count
                        ) ORDER BY grouped.total_kg DESC, grouped.disposal_method NULLS FIRST
                    ), '[]'::JSONB) FROM waste_period_disposal AS grouped
                )
            )
              FROM waste_period_totals AS totals
        ),
        'waste_streams', (
            SELECT COALESCE(
                pg_catalog.jsonb_agg(
                    pg_catalog.jsonb_build_object(
                        'waste_type', grouped.waste_type,
                        'disposal_method', grouped.disposal_method,
                        'quantity_unit', grouped.quantity_unit,
                        'record_count', grouped.record_count,
                        'total_quantity', grouped.total_quantity,
                        'first_date', grouped.first_date,
                        'last_date', grouped.last_date
                    ) ORDER BY grouped.waste_type, grouped.disposal_method NULLS FIRST,
                               grouped.quantity_unit
                ), '[]'::JSONB
            ) FROM waste_groups AS grouped
        ),
        'composting', (
            SELECT COALESCE(
                pg_catalog.jsonb_agg(
                    pg_catalog.jsonb_build_object(
                        'feedstock_type', grouped.feedstock_type,
                        'compost_method', grouped.compost_method,
                        'record_count', grouped.record_count,
                        'feedstock_kg', grouped.feedstock_kg,
                        'total_output_kg', grouped.total_output_kg,
                        'weighted_yield_pct', grouped.weighted_yield_pct,
                        'mean_batch_yield_pct', grouped.mean_batch_yield_pct,
                        'mean_duration_days', grouped.mean_duration_days,
                        'mean_temperature_c', grouped.mean_temperature_c,
                        'mean_moisture_pct', grouped.mean_moisture_pct,
                        'graded_batches', grouped.graded_batches,
                        'first_date', grouped.first_date,
                        'last_date', grouped.last_date
                    ) ORDER BY grouped.feedstock_type, grouped.compost_method
                ), '[]'::JSONB
            ) FROM compost_groups AS grouped
        ),
        'composting_efficiency', (
            SELECT pg_catalog.jsonb_build_object(
                'location_id', requested_location_id::TEXT,
                'total_batches', totals.total_batches,
                'total_feedstock_kg', totals.total_feedstock_kg,
                'total_output_kg', totals.total_output_kg,
                'overall_yield_pct', CASE
                    WHEN totals.total_feedstock_kg > 0 AND totals.total_output_kg > 0
                    THEN pg_catalog.round((
                        totals.total_output_kg / totals.total_feedstock_kg * 100
                    )::NUMERIC, 1)
                    ELSE NULL
                END,
                'by_method', (
                    SELECT COALESCE(pg_catalog.jsonb_agg(
                        pg_catalog.jsonb_build_object(
                            'compost_method', grouped.compost_method,
                            'batches', grouped.batches,
                            'avg_yield_pct', grouped.avg_yield_pct,
                            'avg_feedstock_kg', grouped.avg_feedstock_kg,
                            'avg_output_kg', grouped.avg_output_kg,
                            'avg_duration_days', grouped.avg_duration_days
                        ) ORDER BY grouped.batches DESC, grouped.compost_method
                    ), '[]'::JSONB) FROM compost_method_efficiency AS grouped
                ),
                'recent_quality', (
                    SELECT COALESCE(pg_catalog.jsonb_agg(
                        pg_catalog.jsonb_build_object(
                            'ph', grouped.ph,
                            'moisture_pct', grouped.moisture_pct,
                            'temperature_c', grouped.temperature_c,
                            'output_yield_pct', grouped.output_yield_pct,
                            'recorded_at', grouped.recorded_at
                        ) ORDER BY grouped.recorded_at DESC, grouped.id DESC
                    ), '[]'::JSONB) FROM compost_recent_quality AS grouped
                )
            ) FROM compost_totals AS totals
        ),
        'recycling', (
            SELECT COALESCE(
                pg_catalog.jsonb_agg(
                    pg_catalog.jsonb_build_object(
                        'material_type', grouped.material_type,
                        'record_count', grouped.record_count,
                        'quantity_kg', grouped.quantity_kg,
                        'first_date', grouped.first_date,
                        'last_date', grouped.last_date
                    ) ORDER BY grouped.material_type
                ), '[]'::JSONB
            ) FROM recycling_groups AS grouped
        )
    ) INTO result;
    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.summarize_location_waste_operations(UUID, INTEGER)
    OWNER TO kokonut_waste_summary_reader;
REVOKE ALL ON FUNCTION kokonut_security.summarize_location_waste_operations(UUID, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.summarize_location_waste_operations(UUID, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime'
    ) THEN
        REVOKE ALL ON FUNCTION kokonut_security.summarize_location_waste_operations(UUID, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.summarize_location_waste_operations(UUID, INTEGER)
    IS 'Returns verified location-scoped waste, composting, and recycling aggregates, a bounded waste date window, compost efficiency, and recent numeric quality readings after validating signed operator context and the exact waste_management read grant.';

COMMIT;
