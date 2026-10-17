-- Some signed-worker migrations revoke privileges from optional deployment
-- roles. On a fresh database, create locked placeholders so those REVOKEs are
-- replayable before the corresponding deployment profile is enabled.
DO $bootstrap_roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER '
            || 'NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_login') THEN
        EXECUTE 'CREATE ROLE kokonut_worker_login NOLOGIN NOINHERIT NOSUPERUSER '
            || 'NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;
END;
$bootstrap_roles$;
