-- Evidence maturity is a shared policy vocabulary initialized by schema 029.
-- Runtime changes could alter publication gates across claims, reports, and
-- scoring, so update it only through a reviewed, checksummed schema migration.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.evidence_maturity_level') IS NULL THEN
        RAISE EXCEPTION 'required read-only reference relation public.evidence_maturity_level is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.evidence_maturity_level FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.evidence_maturity_level'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.evidence_maturity_level FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.evidence_maturity_level FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.evidence_maturity_level FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.evidence_maturity_level TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.evidence_maturity_level IS
    'Shared evidence maturity policy vocabulary. kokonut_runtime has read-only access; policy changes require a reviewed reference-data migration.';

COMMIT;
