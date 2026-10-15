-- The runtime role must resolve the qualified, bounded security functions.
-- Restored DB-only checkpoints omit ACLs, so repair this narrow schema grant
-- through the ordered migration stream when the runtime role exists.

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
    END IF;
END;
$$;

COMMIT;
