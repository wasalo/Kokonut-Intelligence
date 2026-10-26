-- Give organic-readiness synthesis its own signed source login and exact
-- location-filtered projections instead of the broad synthesis reader.

BEGIN;

DO $$
DECLARE
    role_name TEXT;
    missing_view TEXT;
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
        SELECT 1
          FROM pg_catalog.pg_roles AS owner_role
         WHERE owner_role.rolname = 'kokonut_agent_summary_source_view_owner'
           AND (
               owner_role.rolcanlogin OR owner_role.rolsuper
               OR owner_role.rolcreatedb OR owner_role.rolcreaterole
               OR owner_role.rolreplication OR owner_role.rolbypassrls
           )
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

    SELECT expected.view_name INTO missing_view
      FROM unnest(ARRAY[
          'organic_readiness_assessment', 'organic_transition_plan',
          'organic_input_audit', 'buffer_zone', 'harvest_handling_record',
          'organic_certification_record', 'organic_compliance_checklist',
          'prohibited_substance_record', 'v_public_organic_readiness',
          'v_public_organic_transition', 'v_public_organic_input_audit',
          'v_public_buffer_zone_status', 'v_public_organic_harvest_segregation',
          'v_public_organic_certifications',
          'v_public_organic_prohibited_substance_audit'
      ]::TEXT[]) AS expected(view_name)
     WHERE pg_catalog.to_regclass(
         pg_catalog.format('kokonut_agent_source.%I', expected.view_name)
     ) IS NULL
     ORDER BY expected.view_name
     LIMIT 1;
    IF missing_view IS NOT NULL THEN
        RAISE EXCEPTION 'organic readiness source projection % from migration 549 is required',
            missing_view;
    END IF;

    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_agent_organic_readiness_reader',
        'kokonut_agent_organic_readiness_login'
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
            RAISE EXCEPTION 'organic readiness source role % has unsafe attributes', role_name;
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
                     'kokonut_agent_organic_readiness_reader',
                     'kokonut_agent_organic_readiness_login'
                 )
                 OR member_role.rolname IN (
                     'kokonut_agent_organic_readiness_reader',
                     'kokonut_agent_organic_readiness_login'
                 )
               )
           AND NOT (
               granted_role.rolname = 'kokonut_agent_organic_readiness_reader'
               AND member_role.rolname = 'kokonut_agent_organic_readiness_login'
               AND membership.admin_option IS FALSE
               AND membership.inherit_option IS FALSE
               AND membership.set_option IS TRUE
           )
    ) THEN
        RAISE EXCEPTION 'organic readiness roles have unexpected memberships';
    END IF;
END;
$$;

GRANT kokonut_agent_organic_readiness_reader
    TO kokonut_agent_organic_readiness_login
    WITH INHERIT FALSE, SET TRUE;

REVOKE ALL ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_security
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_security
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;
REVOKE CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_organic_readiness_reader,
         kokonut_agent_organic_readiness_login;

REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.organic_readiness_assessment,
    kokonut_agent_source.organic_transition_plan,
    kokonut_agent_source.organic_input_audit,
    kokonut_agent_source.buffer_zone,
    kokonut_agent_source.harvest_handling_record,
    kokonut_agent_source.organic_certification_record,
    kokonut_agent_source.organic_compliance_checklist,
    kokonut_agent_source.prohibited_substance_record,
    kokonut_agent_source.v_public_organic_readiness,
    kokonut_agent_source.v_public_organic_transition,
    kokonut_agent_source.v_public_organic_input_audit,
    kokonut_agent_source.v_public_buffer_zone_status,
    kokonut_agent_source.v_public_organic_harvest_segregation,
    kokonut_agent_source.v_public_organic_certifications,
    kokonut_agent_source.v_public_organic_prohibited_substance_audit
FROM PUBLIC,
     kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login,
     kokonut_agent_organic_readiness_reader,
     kokonut_agent_organic_readiness_login;

GRANT USAGE ON SCHEMA kokonut_security
    TO kokonut_agent_organic_readiness_login;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO kokonut_agent_organic_readiness_login;
GRANT USAGE ON SCHEMA kokonut_security, kokonut_agent_source
    TO kokonut_agent_organic_readiness_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_organic_readiness_reader;
GRANT SELECT ON TABLE
    kokonut_agent_source.organic_readiness_assessment,
    kokonut_agent_source.organic_transition_plan,
    kokonut_agent_source.organic_input_audit,
    kokonut_agent_source.buffer_zone,
    kokonut_agent_source.harvest_handling_record,
    kokonut_agent_source.organic_certification_record,
    kokonut_agent_source.organic_compliance_checklist,
    kokonut_agent_source.prohibited_substance_record,
    kokonut_agent_source.v_public_organic_readiness,
    kokonut_agent_source.v_public_organic_transition,
    kokonut_agent_source.v_public_organic_input_audit,
    kokonut_agent_source.v_public_buffer_zone_status,
    kokonut_agent_source.v_public_organic_harvest_segregation,
    kokonut_agent_source.v_public_organic_certifications,
    kokonut_agent_source.v_public_organic_prohibited_substance_audit
TO kokonut_agent_organic_readiness_reader;

DO $$
DECLARE
    unexpected_relation TEXT;
    missing_relation TEXT;
    expected_names TEXT[] := ARRAY[
        'organic_readiness_assessment', 'organic_transition_plan',
        'organic_input_audit', 'buffer_zone', 'harvest_handling_record',
        'organic_certification_record', 'organic_compliance_checklist',
        'prohibited_substance_record', 'v_public_organic_readiness',
        'v_public_organic_transition', 'v_public_organic_input_audit',
        'v_public_buffer_zone_status', 'v_public_organic_harvest_segregation',
        'v_public_organic_certifications',
        'v_public_organic_prohibited_substance_audit'
    ];
BEGIN
    SELECT pg_catalog.string_agg(relation.relname::TEXT, ', ' ORDER BY relation.relname::TEXT)
      INTO unexpected_relation
      FROM pg_catalog.pg_class AS relation
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'kokonut_agent_source'
       AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND pg_catalog.has_table_privilege(
           'kokonut_agent_organic_readiness_reader', relation.oid, 'SELECT'
       )
       AND relation.relname::TEXT <> ALL (expected_names);
    IF unexpected_relation IS NOT NULL THEN
        RAISE EXCEPTION 'organic readiness reader can select unapproved source projections: %',
            unexpected_relation;
    END IF;

    SELECT pg_catalog.string_agg(expected.name, ', ' ORDER BY expected.name)
      INTO missing_relation
      FROM unnest(expected_names) AS expected(name)
     WHERE NOT pg_catalog.has_table_privilege(
         'kokonut_agent_organic_readiness_reader',
         pg_catalog.format('kokonut_agent_source.%I', expected.name), 'SELECT'
     );
    IF missing_relation IS NOT NULL THEN
        RAISE EXCEPTION 'organic readiness reader lacks source projections: %',
            missing_relation;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.unnest(expected_names) AS expected(name)
         WHERE pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_source_reader',
                   pg_catalog.format('kokonut_agent_source.%I', expected.name), 'SELECT'
               )
            OR pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_source_login',
                   pg_catalog.format('kokonut_agent_source.%I', expected.name), 'SELECT'
               )
    ) THEN
        RAISE EXCEPTION 'shared synthesis source roles retain organic readiness projections';
    END IF;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_organic_readiness_reader', 'public.ai_summary', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_organic_readiness_reader',
        'kokonut_agent_source.v_public_capital_efficiency_summary', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_organic_readiness_login',
        'kokonut_agent_source.organic_readiness_assessment', 'SELECT'
    ) OR pg_catalog.has_schema_privilege(
        'kokonut_agent_organic_readiness_login', 'kokonut_agent_source', 'USAGE'
    ) OR NOT pg_catalog.has_function_privilege(
        'kokonut_agent_organic_readiness_login',
        'kokonut_security.set_worker_tenant_context(text,uuid,text,text)', 'EXECUTE'
    ) OR pg_catalog.has_function_privilege(
        'kokonut_agent_organic_readiness_login',
        'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
    ) OR NOT pg_catalog.has_function_privilege(
        'kokonut_agent_organic_readiness_reader',
        'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_organic_readiness_reader',
        'kokonut_agent_source.organic_readiness_assessment', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'organic readiness login/reader exceeds its source contract';
    END IF;
END;
$$;

COMMIT;
