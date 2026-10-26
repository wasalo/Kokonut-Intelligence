-- Give Open Source Capitalist synthesis its own signed source login and reader.
-- Preserve three location-or-network and two network-wide public Open Source Capitalist
-- projections while removing them from the broad synthesis identity.

BEGIN;

DO $$
DECLARE
    role_name TEXT;
    source_name TEXT;
    missing_view TEXT;
    source_views TEXT[] := ARRAY['v_public_farm_launch_unit_economics', 'v_public_adoption_barrier_assessment', 'v_public_perpetual_value_stress_test', 'v_public_network_scaling_target', 'v_public_open_source_impact_artifact'];
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_reader'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_login'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_view_owner'
    ) THEN
        RAISE EXCEPTION 'shared synthesis source roles from migration 541 are required';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles AS owner_role
         WHERE owner_role.rolname = 'kokonut_agent_summary_source_view_owner'
           AND (owner_role.rolcanlogin OR owner_role.rolsuper
                OR owner_role.rolcreatedb OR owner_role.rolcreaterole
                OR owner_role.rolreplication OR owner_role.rolbypassrls)
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_agent_summary_source_view_owner'
            OR member_role.rolname = 'kokonut_agent_summary_source_view_owner'
    ) THEN
        RAISE EXCEPTION 'shared synthesis source view owner must remain disabled and unassigned';
    END IF;

    FOREACH source_name IN ARRAY source_views LOOP
        IF pg_catalog.to_regclass(
            pg_catalog.format('kokonut_agent_source.%I', source_name)
        ) IS NULL THEN
            missing_view := source_name;
            EXIT;
        END IF;
    END LOOP;
    IF missing_view IS NOT NULL THEN
        RAISE EXCEPTION 'Open Source Capitalist synthesis projection % from migrations 534 and 543 is required',
            missing_view;
    END IF;

    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_agent_open_source_capitalist_reader',
        'kokonut_agent_open_source_capitalist_login'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
        ) THEN
            EXECUTE pg_catalog.format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        ELSIF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = role_name
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'Open Source Capitalist synthesis source role % has unsafe attributes', role_name;
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE (
                 granted_role.rolname IN (
                     'kokonut_agent_open_source_capitalist_reader',
                     'kokonut_agent_open_source_capitalist_login'
                 )
                 OR member_role.rolname IN (
                     'kokonut_agent_open_source_capitalist_reader',
                     'kokonut_agent_open_source_capitalist_login'
                 )
               )
           AND NOT (
               granted_role.rolname = 'kokonut_agent_open_source_capitalist_reader'
               AND member_role.rolname = 'kokonut_agent_open_source_capitalist_login'
               AND membership.admin_option IS FALSE
               AND membership.inherit_option IS FALSE
               AND membership.set_option IS TRUE
           )
    ) THEN
        RAISE EXCEPTION 'Open Source Capitalist synthesis roles have unexpected memberships';
    END IF;
END;
$$;

GRANT kokonut_agent_open_source_capitalist_reader
    TO kokonut_agent_open_source_capitalist_login
    WITH INHERIT FALSE, SET TRUE;

REVOKE ALL ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_security
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_security
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;
REVOKE CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_open_source_capitalist_reader,
         kokonut_agent_open_source_capitalist_login;

DO $$
DECLARE
    source_name TEXT;
    source_views TEXT[] := ARRAY['v_public_farm_launch_unit_economics', 'v_public_adoption_barrier_assessment', 'v_public_perpetual_value_stress_test', 'v_public_network_scaling_target', 'v_public_open_source_impact_artifact'];
BEGIN
    FOREACH source_name IN ARRAY source_views LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ALL PRIVILEGES ON TABLE kokonut_agent_source.%I FROM PUBLIC, kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login, kokonut_agent_open_source_capitalist_reader, kokonut_agent_open_source_capitalist_login',
            source_name
        );
        EXECUTE pg_catalog.format(
            'GRANT SELECT ON TABLE kokonut_agent_source.%I TO kokonut_agent_open_source_capitalist_reader',
            source_name
        );
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security
    TO kokonut_agent_open_source_capitalist_login;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO kokonut_agent_open_source_capitalist_login;
GRANT USAGE ON SCHEMA kokonut_security, kokonut_agent_source
    TO kokonut_agent_open_source_capitalist_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_open_source_capitalist_reader;

DO $$
DECLARE
    unexpected_relation TEXT;
    missing_relation TEXT;
    source_name TEXT;
    source_views TEXT[] := ARRAY['v_public_farm_launch_unit_economics', 'v_public_adoption_barrier_assessment', 'v_public_perpetual_value_stress_test', 'v_public_network_scaling_target', 'v_public_open_source_impact_artifact'];
BEGIN
    SELECT pg_catalog.string_agg(relation.relname::TEXT, ', ' ORDER BY relation.relname::TEXT)
      INTO unexpected_relation
      FROM pg_catalog.pg_class AS relation
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'kokonut_agent_source'
       AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND pg_catalog.has_table_privilege(
           'kokonut_agent_open_source_capitalist_reader', relation.oid, 'SELECT'
       )
       AND relation.relname::TEXT <> ALL (source_views);
    IF unexpected_relation IS NOT NULL THEN
        RAISE EXCEPTION 'Open Source Capitalist synthesis reader can select unapproved projections: %',
            unexpected_relation;
    END IF;

    FOREACH source_name IN ARRAY source_views LOOP
        IF NOT pg_catalog.has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader',
            pg_catalog.format('kokonut_agent_source.%I', source_name), 'SELECT'
        ) THEN
            missing_relation := source_name;
            EXIT;
        END IF;
        IF pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_reader',
            pg_catalog.format('kokonut_agent_source.%I', source_name), 'SELECT'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_login',
            pg_catalog.format('kokonut_agent_source.%I', source_name), 'SELECT'
        ) THEN
            RAISE EXCEPTION 'shared synthesis roles retain Open Source Capitalist synthesis projection %',
                source_name;
        END IF;
    END LOOP;
    IF missing_relation IS NOT NULL THEN
        RAISE EXCEPTION 'Open Source Capitalist synthesis reader lacks projection %', missing_relation;
    END IF;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_reader', 'public.ai_summary', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_reader',
        'kokonut_agent_source.v_public_anti_capture_governance_policy', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_reader',
        'kokonut_agent_source.v_public_commons_redistribution_policy', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_login',
        'kokonut_agent_source.v_public_commons_redistribution_policy', 'SELECT'
    ) OR pg_catalog.has_schema_privilege(
        'kokonut_agent_open_source_capitalist_login', 'kokonut_agent_source', 'USAGE'
    ) OR NOT pg_catalog.has_function_privilege(
        'kokonut_agent_open_source_capitalist_login',
        'kokonut_security.set_worker_tenant_context(text,uuid,text,text)', 'EXECUTE'
    ) OR pg_catalog.has_function_privilege(
        'kokonut_agent_open_source_capitalist_login',
        'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
    ) OR NOT pg_catalog.has_function_privilege(
        'kokonut_agent_open_source_capitalist_reader',
        'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_reader', 'public.farm_launch_unit_economics', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_reader', 'public.adoption_barrier_assessment', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_reader', 'public.perpetual_value_stress_test', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_reader', 'public.network_scaling_target', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_login', 'public.open_source_impact_artifact', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_open_source_capitalist_reader',
        'kokonut_agent_source.v_public_commons_redistribution_policy', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'Open Source Capitalist synthesis login/reader exceeds its source contract';
    END IF;
END;
$$;

COMMIT;
