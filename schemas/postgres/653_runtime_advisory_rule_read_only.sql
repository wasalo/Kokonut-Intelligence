-- Advisory rules are shared reference configuration. Application code reads
-- them to produce farm-scoped recommendations; seed/admin processes own edits.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.advisory_rule') IS NULL THEN
        RAISE EXCEPTION 'required read-only relation public.advisory_rule is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.advisory_rule FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.advisory_rule'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.advisory_rule FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.advisory_rule FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.advisory_rule FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.advisory_rule TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.advisory_rule IS
    'Shared advisory reference rules. kokonut_runtime has read-only access; seed/admin processes own rule changes.';

COMMIT;
