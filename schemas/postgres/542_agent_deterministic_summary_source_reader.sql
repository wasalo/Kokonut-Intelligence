-- Isolate deterministic AI-summary source reads from the shared application
-- login. This is a relation-level allowlist, not tenant RLS: the fixed summary
-- queries bind an exact location, and database-enforced tenant context remains
-- a separate acceptance gate.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_deterministic_reader'
    ) THEN
        CREATE ROLE kokonut_agent_summary_deterministic_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_deterministic_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'deterministic summary source-reader role has unsafe attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_deterministic_source_login'
    ) THEN
        CREATE ROLE kokonut_agent_summary_deterministic_source_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_deterministic_source_login'
           AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'deterministic summary source login has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE (member_role.rolname = 'kokonut_agent_summary_deterministic_source_login'
                AND (granted_role.rolname <> 'kokonut_agent_summary_deterministic_reader'
                     OR membership.admin_option OR membership.inherit_option
                     OR NOT membership.set_option))
            OR granted_role.rolname = 'kokonut_agent_summary_deterministic_source_login'
            OR (member_role.rolname = 'kokonut_agent_summary_deterministic_reader'
                AND granted_role.rolname <> 'kokonut_agent_summary_deterministic_source_login')
            OR (granted_role.rolname = 'kokonut_agent_summary_deterministic_reader'
                AND member_role.rolname <> 'kokonut_agent_summary_deterministic_source_login')
    ) THEN
        RAISE EXCEPTION 'deterministic summary source roles have unexpected memberships';
    END IF;
END;
$$;

GRANT kokonut_agent_summary_deterministic_reader
    TO kokonut_agent_summary_deterministic_source_login
    WITH INHERIT FALSE, SET TRUE;
GRANT USAGE ON SCHEMA public TO kokonut_agent_summary_deterministic_reader;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_summary_deterministic_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_summary_deterministic_reader;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_summary_deterministic_reader;

GRANT SELECT ON TABLE
    public.crop,
    public.crop_cycle,
    public.expense_category,
    public.expense_event,
    public.farm_registry_record,
    public.harvest_event,
    public.noi_snapshot,
    public.remote_sensing_observation,
    public.sales_event,
    public.sensor_reading,
    public.soil_carbon_measurement,
    public.species_observation,
    public.weather_observation
    TO kokonut_agent_summary_deterministic_reader;

DO $$
DECLARE
    unapproved_relation TEXT;
    approved_relations TEXT[] := ARRAY[
        'crop',
        'crop_cycle',
        'expense_category',
        'expense_event',
        'farm_registry_record',
        'harvest_event',
        'noi_snapshot',
        'remote_sensing_observation',
        'sales_event',
        'sensor_reading',
        'soil_carbon_measurement',
        'species_observation',
        'weather_observation',
        'geography_columns',
        'geometry_columns',
        'spatial_ref_sys'
    ];
BEGIN
    SELECT pg_catalog.string_agg(rel.relname::text, ', ' ORDER BY rel.relname::text)
      INTO unapproved_relation
      FROM pg_catalog.pg_class AS rel
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = rel.relnamespace
     WHERE namespace.nspname = 'public'
       AND rel.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND pg_catalog.has_table_privilege(
           'kokonut_agent_summary_deterministic_reader', rel.oid, 'SELECT'
       )
       AND rel.relname::text <> ALL (approved_relations);
    IF unapproved_relation IS NOT NULL THEN
        RAISE EXCEPTION
            'deterministic summary source reader can select unapproved public relations: %',
            unapproved_relation;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND (
               pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_deterministic_reader', relation.oid, 'INSERT'
               )
               OR pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_deterministic_reader', relation.oid, 'UPDATE'
               )
               OR pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_deterministic_reader', relation.oid, 'DELETE'
               )
               OR pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_deterministic_reader', relation.oid, 'TRUNCATE'
               )
           )
    ) THEN
        RAISE EXCEPTION 'deterministic summary source reader has public write privileges';
    END IF;

    IF pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_deterministic_reader', 'public', 'CREATE'
    ) THEN
        RAISE EXCEPTION 'deterministic summary source reader can create public objects';
    END IF;
END;
$$;

COMMIT;
