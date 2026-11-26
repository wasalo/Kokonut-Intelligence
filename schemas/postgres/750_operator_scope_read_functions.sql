-- Route operator scope checks and scope listings through the isolated
-- operator-auth login without granting it direct access to tenant tables.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_operator_scope_read_owner'
    ) THEN
        CREATE ROLE kokonut_operator_scope_read_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_operator_scope_read_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'operator scope read owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_operator_scope_read_owner'
            OR member_role.rolname = 'kokonut_operator_scope_read_owner'
    ) THEN
        RAISE EXCEPTION 'operator scope read owner must not have role membership';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
         WHERE relation.relowner = (
             SELECT oid FROM pg_catalog.pg_roles
              WHERE rolname = 'kokonut_operator_scope_read_owner'
         )
           AND relation.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
    ) THEN
        RAISE EXCEPTION 'operator scope read owner must not own database relations';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc AS procedure
         WHERE procedure.proowner = (
             SELECT oid FROM pg_catalog.pg_roles
              WHERE rolname = 'kokonut_operator_scope_read_owner'
         )
           AND procedure.oid IS DISTINCT FROM pg_catalog.to_regprocedure(
               'kokonut_security.operator_scope_grant_read_allows(uuid,text,text,uuid)'
           )
           AND procedure.oid IS DISTINCT FROM pg_catalog.to_regprocedure(
               'kokonut_security.operator_scope_grant_read_scopes(uuid)'
           )
    ) THEN
        RAISE EXCEPTION 'operator scope read owner must own only its two bounded functions';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_operator_scope_read_owner;
REVOKE CREATE ON SCHEMA public, kokonut_security FROM kokonut_operator_scope_read_owner;

-- Reapplication also repairs a pre-existing owner ACL. Remove all object and
-- column-level table privileges before granting the exact read set below.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public, kokonut_security
    FROM kokonut_operator_scope_read_owner;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public, kokonut_security
    FROM kokonut_operator_scope_read_owner;
DO $$
DECLARE
    relation RECORD;
    column_name TEXT;
BEGIN
    FOR relation IN
        SELECT namespace.nspname, class.relname, class.oid
          FROM pg_catalog.pg_class AS class
          JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = class.relnamespace
         WHERE namespace.nspname IN ('public', 'kokonut_security')
           AND class.relkind IN ('r', 'p', 'v', 'm', 'f')
    LOOP
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation.oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE %2$I.%3$I FROM kokonut_operator_scope_read_owner',
                column_name, relation.nspname, relation.relname
            );
        END LOOP;
    END LOOP;
END;
$$;

-- The non-login function owner can inspect only the columns needed to answer
-- the existing tenant-aware scope predicate and to return a caller's scopes.
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_operator_scope_read_owner;
GRANT SELECT (id, enabled)
    ON TABLE public.operator_identity TO kokonut_operator_scope_read_owner;
GRANT SELECT (id, organization_id)
    ON TABLE public.location TO kokonut_operator_scope_read_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_operator_scope_read_owner;
GRANT SELECT (id, status)
    ON TABLE public.organization TO kokonut_operator_scope_read_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_operator_scope_read_owner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share TO kokonut_operator_scope_read_owner;

-- These policies are dormant until a relation enables RLS. If FORCE RLS is
-- enabled later, only this isolated function owner receives the SELECT rows
-- required by its fixed, bounded functions.
DO $$
DECLARE
    relation_name TEXT;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'operator_scope_grant',
        'operator_identity',
        'location',
        'operator_organization_membership',
        'organization',
        'location_tenant_owner_verification',
        'location_organization_share'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = 'public'
               AND tablename = relation_name
               AND policyname = 'operator_scope_read_owner_select'
        ) THEN
            EXECUTE pg_catalog.format(
                'CREATE POLICY operator_scope_read_owner_select ON public.%I '
                'FOR SELECT TO kokonut_operator_scope_read_owner USING (true)',
                relation_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.operator_scope_grant_read_allows(
    requested_operator_id UUID,
    requested_resource TEXT,
    requested_action TEXT,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM public.operator_scope_grant AS grant_row
          JOIN public.operator_identity AS identity
            ON identity.id = grant_row.operator_id AND identity.enabled
          JOIN public.location AS loc ON loc.id = grant_row.location_id
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
           AND (
               grant_row.organization_id IS NULL
               OR (
                   grant_row.organization_id IS NOT NULL
                   AND EXISTS (
                       SELECT 1
                         FROM public.operator_organization_membership AS membership
                         JOIN public.organization AS tenant
                           ON tenant.id = membership.organization_id
                          AND tenant.status = 'active'
                        WHERE membership.operator_id = grant_row.operator_id
                          AND membership.organization_id = grant_row.organization_id
                          AND membership.revoked_at IS NULL
                   )
                   AND EXISTS (
                       SELECT 1
                         FROM public.location_tenant_owner_verification AS owner
                        WHERE owner.location_id = loc.id
                          AND owner.organization_id = loc.organization_id
                          AND owner.revoked_at IS NULL
                          AND (
                              owner.organization_id = grant_row.organization_id
                              OR EXISTS (
                                  SELECT 1
                                    FROM public.location_organization_share AS share
                                   WHERE share.location_id = loc.id
                                     AND share.organization_id = grant_row.organization_id
                                     AND share.revoked_at IS NULL
                                     AND (share.expires_at IS NULL
                                          OR share.expires_at > pg_catalog.now())
                              )
                          )
                   )
               )
           )
    );
$$;

CREATE OR REPLACE FUNCTION kokonut_security.operator_scope_grant_read_scopes(
    requested_operator_id UUID
)
RETURNS TABLE(resource TEXT, action TEXT, location_id UUID)
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT grant_row.resource, grant_row.action, grant_row.location_id
      FROM public.operator_scope_grant AS grant_row
     WHERE grant_row.operator_id = requested_operator_id
       AND grant_row.revoked_at IS NULL
       AND kokonut_security.operator_scope_grant_read_allows(
               grant_row.operator_id,
               grant_row.resource,
               grant_row.action,
               grant_row.location_id
           )
     ORDER BY grant_row.resource, grant_row.action, grant_row.location_id
$$;

ALTER FUNCTION kokonut_security.operator_scope_grant_read_allows(UUID, TEXT, TEXT, UUID)
    OWNER TO kokonut_operator_scope_read_owner;
ALTER FUNCTION kokonut_security.operator_scope_grant_read_scopes(UUID)
    OWNER TO kokonut_operator_scope_read_owner;

REVOKE ALL ON FUNCTION kokonut_security.operator_scope_grant_read_allows(UUID, TEXT, TEXT, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.operator_scope_grant_read_scopes(UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.operator_scope_grant_read_allows(
            UUID, TEXT, TEXT, UUID
        ) FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.operator_scope_grant_read_scopes(UUID)
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_operator_auth;
        GRANT EXECUTE ON FUNCTION kokonut_security.operator_scope_grant_read_allows(
            UUID, TEXT, TEXT, UUID
        ) TO kokonut_operator_auth;
        GRANT EXECUTE ON FUNCTION kokonut_security.operator_scope_grant_read_scopes(UUID)
            TO kokonut_operator_auth;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.operator_scope_grant_read_allows(UUID, TEXT, TEXT, UUID) IS
    'Bounded operator-auth scope check preserving the tenant-aware predicate without login table reads.';
COMMENT ON FUNCTION kokonut_security.operator_scope_grant_read_scopes(UUID) IS
    'Returns the active tenant-valid scopes for one operator in stable resource/action/location order.';

COMMIT;
