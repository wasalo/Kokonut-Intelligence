-- Public holistic-wellbeing summaries are report projections, not writer
-- surfaces. Preserve runtime SELECT and underlying observation write paths.
BEGIN;

DO $$
DECLARE
    relation_oid regclass := pg_catalog.to_regclass(
        'public.v_public_wellbeing_metric_summary'
    );
    column_name text;
BEGIN
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.v_public_wellbeing_metric_summary is missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class
         WHERE oid = relation_oid AND relkind = 'v'
    ) THEN
        RAISE EXCEPTION 'public.v_public_wellbeing_metric_summary must remain a view';
    END IF;
    IF pg_catalog.pg_relation_is_updatable(relation_oid, TRUE) <> 0 THEN
        RAISE EXCEPTION 'public.v_public_wellbeing_metric_summary must remain non-updatable';
    END IF;

    REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
        ON TABLE public.v_public_wellbeing_metric_summary FROM PUBLIC;
    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = relation_oid
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
            'ON TABLE public.v_public_wellbeing_metric_summary FROM PUBLIC', column_name
        );
    END LOOP;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.v_public_wellbeing_metric_summary
            FROM kokonut_runtime;
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.v_public_wellbeing_metric_summary FROM kokonut_runtime',
                column_name
            );
        END LOOP;
        GRANT SELECT ON TABLE public.v_public_wellbeing_metric_summary TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON VIEW public.v_public_wellbeing_metric_summary IS
    'Published wellbeing metric report projection; kokonut_runtime may read but not mutate this non-updatable view. Underlying observation writes retain their existing scoped service paths.';

COMMIT;
