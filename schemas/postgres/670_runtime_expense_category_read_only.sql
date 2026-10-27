-- Expense categories are governed shared taxonomy. The Kernel runtime reads
-- them to classify financial facts; new taxonomy entries use an administrative
-- path rather than implicit service writes.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.expense_category');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.expense_category is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.expense_category FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.expense_category FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.expense_category FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.expense_category FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.expense_category TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.expense_category IS
    'Governed shared expense taxonomy. kokonut_runtime has read-only access; taxonomy changes use an administrative path.';

COMMIT;
