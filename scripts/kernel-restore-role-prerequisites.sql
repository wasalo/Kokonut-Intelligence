-- Apply as a PostgreSQL superuser before restoring a DB-only Kernel archive.
-- pg_dump archives RLS policies but intentionally omit cluster-global roles;
-- these NOLOGIN roles must exist before pg_restore can recreate their policies.
BEGIN;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_mobile_credential_owner',
        'kokonut_mobile_context_owner',
        'kokonut_operator_context_owner',
        'kokonut_operator_auth_owner',
        'kokonut_gateway_context_owner',
        'kokonut_mobile_device_revoke_owner'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        ELSIF EXISTS (
            SELECT 1 FROM pg_roles
             WHERE rolname = role_name
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'security function owner % has unsafe role attributes', role_name;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_auth_members AS membership
              JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
              JOIN pg_roles AS member_role ON member_role.oid = membership.member
             WHERE granted_role.rolname = role_name OR member_role.rolname = role_name
        ) THEN
            RAISE EXCEPTION 'security function owner % has role membership', role_name;
        END IF;
    END LOOP;
END;
$$;

COMMIT;
