-- Event delivery through the notification outbox replaced these legacy
-- freshness-attempt rows. Preserve historical reads, but keep the shared
-- application login from creating or changing them directly.
-- Directus, maintenance, and migration-owner grants remain unchanged.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
    relation_kind "char";
BEGIN
    relation_oid := pg_catalog.to_regclass(
        'public.data_freshness_alert_delivery_attempt'
    );
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION
            'required relation public.data_freshness_alert_delivery_attempt is missing';
    END IF;

    SELECT relation.relkind
      INTO relation_kind
      FROM pg_catalog.pg_class AS relation
     WHERE relation.oid = relation_oid;
    IF relation_kind NOT IN ('r', 'p') THEN
        RAISE EXCEPTION
            'public.data_freshness_alert_delivery_attempt must remain a table';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        REVOKE ALL PRIVILEGES ON TABLE
            public.data_freshness_alert_delivery_attempt FROM kokonut_runtime;

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.data_freshness_alert_delivery_attempt '
                'FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE
            public.data_freshness_alert_delivery_attempt TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.data_freshness_alert_delivery_attempt IS
    'Legacy freshness delivery attempts are retained for historical reads. New delivery attempts are owned by notification_outbox. kokonut_runtime has SELECT only; Directus, maintenance, and migration-owner grants are unchanged.';

COMMIT;
