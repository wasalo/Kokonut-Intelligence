-- Currency definitions are shared reference data installed by the ordered
-- finance schema. Runtime services read them but have no application write
-- path; currency additions or metadata corrections use reviewed migrations.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.dfs_currency');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.dfs_currency is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.dfs_currency FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.dfs_currency FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.dfs_currency FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.dfs_currency FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.dfs_currency TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.dfs_currency IS
    'Shared currency reference catalog. kokonut_runtime has read-only access; currency definitions change through reviewed migrations.';

COMMIT;
