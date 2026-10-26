-- Disable the historical shared synthesis source principal after every
-- operational projection has moved to a task-specific reader.

BEGIN;

DO $$
DECLARE
    unexpected_membership TEXT;
    shared_login_oid OID;
    shared_reader_oid OID;
BEGIN
    SELECT oid INTO shared_login_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = 'kokonut_agent_summary_source_login';
    SELECT oid INTO shared_reader_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = 'kokonut_agent_summary_source_reader';

    IF shared_login_oid IS NULL OR shared_reader_oid IS NULL THEN
        RAISE EXCEPTION 'historical shared agent source roles are required';
    END IF;

    SELECT pg_catalog.string_agg(
               pg_catalog.format('%I -> %I', granted_role.rolname, member_role.rolname),
               ', ' ORDER BY granted_role.rolname, member_role.rolname
           )
      INTO unexpected_membership
      FROM pg_catalog.pg_auth_members AS membership
      JOIN pg_catalog.pg_roles AS granted_role
        ON granted_role.oid = membership.roleid
      JOIN pg_catalog.pg_roles AS member_role
        ON member_role.oid = membership.member
     WHERE (membership.roleid = shared_reader_oid
            OR membership.member = shared_reader_oid
            OR membership.roleid = shared_login_oid
            OR membership.member = shared_login_oid)
       AND NOT (
           membership.roleid = shared_reader_oid
           AND membership.member = shared_login_oid
           AND membership.admin_option IS FALSE
           AND membership.inherit_option IS FALSE
           AND membership.set_option IS TRUE
       );
    IF unexpected_membership IS NOT NULL THEN
        RAISE EXCEPTION 'shared agent source roles have unexpected memberships: %',
            unexpected_membership;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
         WHERE relation.relowner IN (shared_login_oid, shared_reader_oid)
        UNION ALL
        SELECT 1
          FROM pg_catalog.pg_proc AS routine
         WHERE routine.proowner IN (shared_login_oid, shared_reader_oid)
        UNION ALL
        SELECT 1
          FROM pg_catalog.pg_namespace AS namespace
         WHERE namespace.nspowner IN (shared_login_oid, shared_reader_oid)
    ) THEN
        RAISE EXCEPTION 'shared agent source roles own database objects';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_default_acl AS default_acl
          CROSS JOIN LATERAL pg_catalog.aclexplode(default_acl.defaclacl) AS acl
         WHERE acl.grantee IN (shared_login_oid, shared_reader_oid)
    ) THEN
        RAISE EXCEPTION 'shared agent source roles appear in default privileges';
    END IF;
END;
$$;

ALTER ROLE kokonut_agent_summary_source_login
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE kokonut_agent_summary_source_reader
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

REVOKE kokonut_agent_summary_source_reader
    FROM kokonut_agent_summary_source_login;

REVOKE ALL PRIVILEGES ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;

DO $$
DECLARE
    shared_login_oid OID;
    shared_reader_oid OID;
BEGIN
    SELECT oid INTO shared_login_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = 'kokonut_agent_summary_source_login';
    SELECT oid INTO shared_reader_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = 'kokonut_agent_summary_source_reader';

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
         WHERE membership.roleid IN (shared_login_oid, shared_reader_oid)
            OR membership.member IN (shared_login_oid, shared_reader_oid)
    ) THEN
        RAISE EXCEPTION 'shared agent source roles retain a role membership';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM (
              SELECT relation.relacl AS acl
                FROM pg_catalog.pg_class AS relation
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = relation.relnamespace
               WHERE namespace.nspname IN ('public', 'kokonut_security', 'kokonut_agent_source')
              UNION ALL
              SELECT routine.proacl
                FROM pg_catalog.pg_proc AS routine
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = routine.pronamespace
               WHERE namespace.nspname IN ('public', 'kokonut_security', 'kokonut_agent_source')
              UNION ALL
              SELECT namespace.nspacl
                FROM pg_catalog.pg_namespace AS namespace
               WHERE namespace.nspname IN ('public', 'kokonut_security', 'kokonut_agent_source')
          ) AS object_acl
          CROSS JOIN LATERAL pg_catalog.aclexplode(object_acl.acl) AS acl
         WHERE acl.grantee IN (shared_login_oid, shared_reader_oid)
    ) THEN
        RAISE EXCEPTION 'shared agent source roles retain direct object privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS role
         WHERE role.oid IN (shared_login_oid, shared_reader_oid)
           AND (role.rolcanlogin OR role.rolsuper OR role.rolcreatedb
                OR role.rolcreaterole OR role.rolreplication OR role.rolbypassrls
                OR role.rolinherit)
    ) THEN
        RAISE EXCEPTION 'shared agent source roles retain unsafe role attributes';
    END IF;
END;
$$;

COMMIT;
