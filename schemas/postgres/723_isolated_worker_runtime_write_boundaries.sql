-- Keep dispatcher and freshness output writes behind their dedicated bounded
-- database functions. Operator/reporting reads remain available to the runtime.
BEGIN;

DO $$
DECLARE
    relation_name TEXT;
    relation_oid REGCLASS;
    column_name TEXT;
    target_relations CONSTANT TEXT[] := ARRAY[
        'event_handler_delivery',
        'event_handler_log',
        'data_freshness_check',
        'data_freshness_alert_state',
        'data_freshness_alert_history',
        'notification_outbox_attempt'
    ];
BEGIN
    FOREACH relation_name IN ARRAY target_relations LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', relation_name)
        );
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required isolated-worker relation public.% is missing',
                relation_name;
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime',
                relation_name
            );

            -- Table-level REVOKE does not clear column grants from earlier
            -- provisioner versions. Remove those explicitly before restoring
            -- the relation's read-only compatibility surface.
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = relation_oid
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I), '
                    'REFERENCES (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    relation_name
                );
            END LOOP;

            EXECUTE pg_catalog.format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_runtime',
                relation_name
            );
        END IF;

        EXECUTE pg_catalog.format(
            'COMMENT ON TABLE public.%I IS %L',
            relation_name,
            'Worker-owned state; kokonut_runtime may read but writes use dedicated bounded functions.'
        );
    END LOOP;

    -- Preserve existing task cadence and user settings, moving only the known
    -- legacy data-freshness entrypoint to its isolated implementation.
    UPDATE public.scheduled_task
       SET module_path = 'services.ingestion.freshness_worker',
           updated_at = NOW()
     WHERE name = 'data_freshness_check'
       AND module_path IN (
           'services.ingestion.data_freshness',
           'services.ingestion.freshness_worker'
       )
       AND command_args = '["--check"]'::jsonb;
END;
$$;

COMMIT;
