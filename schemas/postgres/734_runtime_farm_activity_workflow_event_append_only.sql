-- Keep the Field Collector workflow ledger readable and appendable by the
-- shared runtime identity, but never directly mutable or deletable. Lifecycle
-- triggers and the authenticated Gateway remain responsible for valid inserts.
-- This narrows DML privileges; it does not establish tenant isolation.

BEGIN;

DO $$
DECLARE
    relation_oid REGCLASS := pg_catalog.to_regclass(
        'public.farm_activity_workflow_event'
    );
    column_name TEXT;
BEGIN
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.farm_activity_workflow_event is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        REVOKE ALL PRIVILEGES ON TABLE public.farm_activity_workflow_event
            FROM kokonut_runtime;

        -- Table-level revokes do not clear stale per-column grants.
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I), '
                'REFERENCES (%1$I) '
                'ON TABLE public.farm_activity_workflow_event FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        -- Preserve the current Gateway contract exactly.
        GRANT SELECT, INSERT ON TABLE public.farm_activity_workflow_event
            TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.farm_activity_workflow_event IS
    'Append-only operator actions for Field Collector farm activity promotion and governed lifecycle transitions; shared runtime retains SELECT/INSERT only. This ACL does not establish tenant isolation.';

COMMIT;
