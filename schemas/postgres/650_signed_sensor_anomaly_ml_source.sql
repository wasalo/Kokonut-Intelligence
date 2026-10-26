-- Isolate manual/one-shot ML anomaly analysis behind a signed exact-location
-- source view. This identity is read-only and is distinct from the event-driven
-- anomaly worker, which can create alerts and durable effects.

BEGIN;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_sensor_anomaly_ml_source_view_owner',
        'kokonut_sensor_anomaly_ml_reader',
        'kokonut_sensor_anomaly_ml_source_login'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
        ) THEN
            EXECUTE pg_catalog.format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        ELSIF role_name <> 'kokonut_sensor_anomaly_ml_source_login' AND EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = role_name
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'sensor anomaly ML role % has unsafe attributes', role_name;
        ELSIF role_name = 'kokonut_sensor_anomaly_ml_source_login' AND EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = role_name
               AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                    OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'sensor anomaly ML source login has unsafe attributes';
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE (
             granted_role.rolname IN (
                 'kokonut_sensor_anomaly_ml_reader',
                 'kokonut_sensor_anomaly_ml_source_login'
             ) OR member_role.rolname IN (
                 'kokonut_sensor_anomaly_ml_reader',
                 'kokonut_sensor_anomaly_ml_source_login'
             )
         ) AND NOT (
             granted_role.rolname = 'kokonut_sensor_anomaly_ml_reader'
             AND member_role.rolname = 'kokonut_sensor_anomaly_ml_source_login'
             AND membership.admin_option IS FALSE
             AND membership.inherit_option IS FALSE
             AND membership.set_option IS TRUE
         )
    ) THEN
        RAISE EXCEPTION 'sensor anomaly ML roles have unexpected memberships';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_sensor_anomaly_ml_source_view_owner'
            OR member_role.rolname = 'kokonut_sensor_anomaly_ml_source_view_owner'
    ) THEN
        RAISE EXCEPTION 'sensor anomaly ML source-view owner must have no memberships';
    END IF;
END;
$$;

GRANT kokonut_sensor_anomaly_ml_reader
    TO kokonut_sensor_anomaly_ml_source_login
    WITH INHERIT FALSE, SET TRUE;

CREATE SCHEMA IF NOT EXISTS kokonut_anomaly_ml_source;
REVOKE ALL ON SCHEMA kokonut_anomaly_ml_source FROM PUBLIC,
    kokonut_sensor_anomaly_ml_reader,
    kokonut_sensor_anomaly_ml_source_login;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_sensor_anomaly_ml_source_view_owner;
GRANT USAGE ON SCHEMA kokonut_security
    TO kokonut_sensor_anomaly_ml_reader,
       kokonut_sensor_anomaly_ml_source_login;
GRANT CREATE ON SCHEMA kokonut_anomaly_ml_source
    TO kokonut_sensor_anomaly_ml_source_view_owner;
GRANT USAGE ON SCHEMA kokonut_anomaly_ml_source
    TO kokonut_sensor_anomaly_ml_reader;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_anomaly_ml_source
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_anomaly_ml_source
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_anomaly_ml_source
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_security
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_security
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;
REVOKE CREATE ON SCHEMA public, kokonut_security, kokonut_anomaly_ml_source
    FROM kokonut_sensor_anomaly_ml_reader,
         kokonut_sensor_anomaly_ml_source_login;

GRANT USAGE ON SCHEMA kokonut_security
    TO kokonut_sensor_anomaly_ml_source_login;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO kokonut_sensor_anomaly_ml_source_login;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_sensor_anomaly_ml_source_view_owner,
       kokonut_sensor_anomaly_ml_reader;

GRANT SELECT (
    id, sensor_id, sensor_type, value, reading_date, reading_time,
    location_id, quality
) ON TABLE public.sensor_reading
TO kokonut_sensor_anomaly_ml_source_view_owner;
GRANT SELECT (id, location_id, slug)
    ON TABLE public.sensor_device
TO kokonut_sensor_anomaly_ml_source_view_owner;

-- When these tables are protected by RLS, the view owner can see only rows in
-- the same signed sensor_anomaly_ml/analyze scope that the view enforces.
DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['sensor_reading', 'sensor_device'] LOOP
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'public'
               AND relation.relname = table_name
               AND relation.relrowsecurity
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = 'public'
               AND tablename = table_name
               AND policyname = 'sensor_anomaly_ml_source_select'
        ) THEN
            EXECUTE pg_catalog.format(
                'CREATE POLICY sensor_anomaly_ml_source_select ON public.%I '
                || 'FOR SELECT TO kokonut_sensor_anomaly_ml_source_view_owner '
                || 'USING (EXISTS (SELECT 1 '
                || 'FROM kokonut_security.current_worker_scope(''sensor_anomaly_ml'', ''analyze'') AS scope '
                || 'WHERE scope.location_id = public.%I.location_id))',
                table_name,
                table_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE VIEW kokonut_anomaly_ml_source.sensor_reading
WITH (security_barrier = true) AS
SELECT reading.location_id,
       reading.sensor_id,
       reading.sensor_type::TEXT AS sensor_type,
       reading.value,
       reading.reading_date,
       reading.reading_time,
       reading.quality::TEXT AS quality,
       device.slug AS device_slug
  FROM public.sensor_reading AS reading
  JOIN public.sensor_device AS device
    ON device.id = reading.sensor_id
   AND device.location_id = reading.location_id
 WHERE reading.quality IN ('good', 'estimated')
   AND EXISTS (
       SELECT 1
         FROM kokonut_security.current_worker_scope('sensor_anomaly_ml', 'analyze') AS scope
        WHERE scope.location_id = reading.location_id
   );

ALTER VIEW kokonut_anomaly_ml_source.sensor_reading
    OWNER TO kokonut_sensor_anomaly_ml_source_view_owner;
REVOKE ALL PRIVILEGES ON TABLE kokonut_anomaly_ml_source.sensor_reading
    FROM PUBLIC, kokonut_sensor_anomaly_ml_source_login;
GRANT SELECT ON TABLE kokonut_anomaly_ml_source.sensor_reading
    TO kokonut_sensor_anomaly_ml_reader;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_sensor_anomaly_ml_reader',
        'kokonut_sensor_anomaly_ml_source_login'
    ] LOOP
        IF pg_catalog.has_table_privilege(
            role_name, 'public.sensor_reading', 'SELECT'
        ) OR pg_catalog.has_table_privilege(
            role_name, 'public.sensor_device', 'SELECT'
        ) OR pg_catalog.has_table_privilege(
            role_name, 'public.sensor_reading', 'INSERT'
        ) OR pg_catalog.has_table_privilege(
            role_name, 'kokonut_anomaly_ml_source.sensor_reading', 'UPDATE'
        ) THEN
            RAISE EXCEPTION 'sensor anomaly ML role % exceeds its table boundary', role_name;
        END IF;
    END LOOP;

    IF NOT pg_catalog.has_table_privilege(
        'kokonut_sensor_anomaly_ml_reader',
        'kokonut_anomaly_ml_source.sensor_reading', 'SELECT'
    ) OR pg_catalog.has_schema_privilege(
        'kokonut_sensor_anomaly_ml_source_login',
        'kokonut_anomaly_ml_source', 'USAGE'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_sensor_anomaly_ml_source_login',
        'kokonut_anomaly_ml_source.sensor_reading', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'sensor anomaly ML login cannot be restricted to its reader role';
    END IF;
END;
$$;

COMMENT ON VIEW kokonut_anomaly_ml_source.sensor_reading IS
    'Read-only sensor time series and device slug for the exact signed sensor_anomaly_ml/analyze location.';

COMMIT;
