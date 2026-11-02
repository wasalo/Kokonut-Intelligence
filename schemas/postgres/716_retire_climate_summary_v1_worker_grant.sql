-- The signed climate worker now writes through the audited v2 boundary.
-- Keep the legacy function definition for historical compatibility, but do
-- not leave its older, less-audited entry point callable by application roles.

BEGIN;

REVOKE ALL ON FUNCTION kokonut_security.store_climate_summary(
    UUID, TEXT, JSONB, INTEGER, TEXT
) FROM PUBLIC, kokonut_worker_execution, kokonut_runtime;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.store_climate_summary('
            'UUID, TEXT, JSONB, INTEGER, TEXT) FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.store_climate_summary(
    UUID, TEXT, JSONB, INTEGER, TEXT
) IS
    'Legacy climate writer retained for compatibility but unavailable to application roles; signed workers use store_climate_summary_v2.';

COMMIT;
