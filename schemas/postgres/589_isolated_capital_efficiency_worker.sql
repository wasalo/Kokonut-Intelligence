-- Give Capital efficiency synthesis its own signed source login and reader.
-- Preserve the four location-filtered regeneration, governance, replication, and
-- stewardship projections required by the task while removing them from the broad synthesis identity.

BEGIN;

DO $$
DECLARE
    role_name TEXT;
    source_name TEXT;
    missing_view TEXT;
    source_views TEXT[] := ARRAY['v_public_capital_efficiency_summary', 'v_public_regenerative_efficiency_summary', 'v_public_governance_throughput_summary', 'v_public_capital_provider_utility_summary'];
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
        RAISE EXCEPTION 'Capital efficiency synthesis projection % from migrations 531 and 543 is required',
            missing_view;
    END IF;

    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_agent_capital_efficiency_reader',
        'kokonut_agent_capital_efficiency_login'
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
            RAISE EXCEPTION 'Capital efficiency synthesis source role % has unsafe attributes', role_name;
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
                     'kokonut_agent_capital_efficiency_reader',
                     'kokonut_agent_capital_efficiency_login'
                 )
                 OR member_role.rolname IN (
                     'kokonut_agent_capital_efficiency_reader',
                     'kokonut_agent_capital_efficiency_login'
                 )
               )
           AND NOT (
               granted_role.rolname = 'kokonut_agent_capital_efficiency_reader'
               AND member_role.rolname = 'kokonut_agent_capital_efficiency_login'
               AND membership.admin_option IS FALSE
               AND membership.inherit_option IS FALSE
               AND membership.set_option IS TRUE
           )
    ) THEN
        RAISE EXCEPTION 'Capital efficiency synthesis roles have unexpected memberships';
    END IF;
END;
$$;

GRANT kokonut_agent_capital_efficiency_reader
    TO kokonut_agent_capital_efficiency_login
    WITH INHERIT FALSE, SET TRUE;

REVOKE ALL ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_security
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_security
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;
REVOKE CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_capital_efficiency_reader,
         kokonut_agent_capital_efficiency_login;

DO $$
DECLARE
    source_name TEXT;
    source_views TEXT[] := ARRAY['v_public_capital_efficiency_summary', 'v_public_regenerative_efficiency_summary', 'v_public_governance_throughput_summary', 'v_public_capital_provider_utility_summary'];
BEGIN
    FOREACH source_name IN ARRAY source_views LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ALL PRIVILEGES ON TABLE kokonut_agent_source.%I FROM PUBLIC, kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login, kokonut_agent_capital_efficiency_reader, kokonut_agent_capital_efficiency_login',
            source_name
        );
        EXECUTE pg_catalog.format(
            'GRANT SELECT ON TABLE kokonut_agent_source.%I TO kokonut_agent_capital_efficiency_reader',
            source_name
        );
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security
    TO kokonut_agent_capital_efficiency_login;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO kokonut_agent_capital_efficiency_login;
GRANT USAGE ON SCHEMA kokonut_security, kokonut_agent_source
    TO kokonut_agent_capital_efficiency_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_capital_efficiency_reader;

DO $$
DECLARE
    unexpected_relation TEXT;
    missing_relation TEXT;
    source_name TEXT;
    source_views TEXT[] := ARRAY['v_public_capital_efficiency_summary', 'v_public_regenerative_efficiency_summary', 'v_public_governance_throughput_summary', 'v_public_capital_provider_utility_summary'];
BEGIN
    SELECT pg_catalog.string_agg(relation.relname::TEXT, ', ' ORDER BY relation.relname::TEXT)
      INTO unexpected_relation
      FROM pg_catalog.pg_class AS relation
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'kokonut_agent_source'
       AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND pg_catalog.has_table_privilege(
           'kokonut_agent_capital_efficiency_reader', relation.oid, 'SELECT'
       )
       AND relation.relname::TEXT <> ALL (source_views);
    IF unexpected_relation IS NOT NULL THEN
        RAISE EXCEPTION 'Capital efficiency synthesis reader can select unapproved projections: %',
            unexpected_relation;
    END IF;

    FOREACH source_name IN ARRAY source_views LOOP
        IF NOT pg_catalog.has_table_privilege(
            'kokonut_agent_capital_efficiency_reader',
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
            RAISE EXCEPTION 'shared synthesis roles retain Capital efficiency synthesis projection %',
                source_name;
        END IF;
    END LOOP;
    IF missing_relation IS NOT NULL THEN
        RAISE EXCEPTION 'Capital efficiency synthesis reader lacks projection %', missing_relation;
    END IF;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_capital_efficiency_reader', 'public.ai_summary', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_capital_efficiency_reader',
        'kokonut_agent_source.organic_readiness_assessment', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_capital_efficiency_reader',
        'kokonut_agent_source.v_public_cultural_context_summary', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_capital_efficiency_login',
        'kokonut_agent_source.ecological_interaction', 'SELECT'
    ) OR pg_catalog.has_schema_privilege(
        'kokonut_agent_capital_efficiency_login', 'kokonut_agent_source', 'USAGE'
    ) OR NOT pg_catalog.has_function_privilege(
        'kokonut_agent_capital_efficiency_login',
        'kokonut_security.set_worker_tenant_context(text,uuid,text,text)', 'EXECUTE'
    ) OR pg_catalog.has_function_privilege(
        'kokonut_agent_capital_efficiency_login',
        'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
    ) OR NOT pg_catalog.has_function_privilege(
        'kokonut_agent_capital_efficiency_reader',
        'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_capital_efficiency_reader', 'public.capital_efficiency_scenario', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_capital_efficiency_login', 'public.capital_provider_utility_scenario', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_capital_efficiency_reader',
        'kokonut_agent_source.v_public_cultural_context_summary', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'Capital efficiency synthesis login/reader exceeds its source contract';
    END IF;
END;
$$;

COMMIT;
