-- Restrict direct reads of the Gateway farm-activity audit ledger to the
-- authenticated operator's signed location context. The ledger remains
-- append-only: its SECURITY DEFINER trigger owner can append only under the
-- same signed actor/location context, and runtime retains SELECT only.

BEGIN;

DO $$
DECLARE
    relation_oid REGCLASS := pg_catalog.to_regclass(
        'public.farm_activity_operator_event'
    );
    relation_kind "char";
    event_owner RECORD;
    context_accessor RECORD;
    column_name TEXT;
BEGIN
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.farm_activity_operator_event is missing';
    END IF;

    SELECT relation.relkind
      INTO relation_kind
      FROM pg_catalog.pg_class AS relation
     WHERE relation.oid = relation_oid;
    IF relation_kind IS DISTINCT FROM 'r' THEN
        RAISE EXCEPTION 'public.farm_activity_operator_event must remain a table';
    END IF;

    SELECT role.rolcanlogin, role.rolsuper, role.rolcreatedb,
           role.rolcreaterole, role.rolreplication, role.rolbypassrls,
           role.rolinherit
      INTO event_owner
      FROM pg_catalog.pg_roles AS role
     WHERE role.rolname = 'kokonut_farm_activity_event_owner';
    IF NOT FOUND OR event_owner.rolcanlogin OR event_owner.rolsuper
       OR event_owner.rolcreatedb OR event_owner.rolcreaterole
       OR event_owner.rolreplication OR event_owner.rolbypassrls
       OR event_owner.rolinherit THEN
        RAISE EXCEPTION 'farm activity event function owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_farm_activity_event_owner'
            OR member_role.rolname = 'kokonut_farm_activity_event_owner'
    ) THEN
        RAISE EXCEPTION 'farm activity event function owner must not have role memberships';
    END IF;

    IF ARRAY[
        pg_catalog.has_table_privilege(
            'kokonut_farm_activity_event_owner', relation_oid, 'SELECT'
        ),
        pg_catalog.has_table_privilege(
            'kokonut_farm_activity_event_owner', relation_oid, 'INSERT'
        ),
        pg_catalog.has_table_privilege(
            'kokonut_farm_activity_event_owner', relation_oid, 'UPDATE'
        ),
        pg_catalog.has_table_privilege(
            'kokonut_farm_activity_event_owner', relation_oid, 'DELETE'
        ),
        pg_catalog.has_table_privilege(
            'kokonut_farm_activity_event_owner', relation_oid, 'TRUNCATE'
        ),
        pg_catalog.has_table_privilege(
            'kokonut_farm_activity_event_owner', relation_oid, 'REFERENCES'
        ),
        pg_catalog.has_table_privilege(
            'kokonut_farm_activity_event_owner', relation_oid, 'TRIGGER'
        )
    ] IS DISTINCT FROM ARRAY[TRUE, TRUE, FALSE, FALSE, FALSE, FALSE, FALSE] THEN
        RAISE EXCEPTION 'farm activity event function owner must retain only SELECT and INSERT';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = relation_oid
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
           AND (
               pg_catalog.has_column_privilege(
                   'kokonut_farm_activity_event_owner', relation_oid,
                   attribute.attname, 'UPDATE'
               )
               OR pg_catalog.has_column_privilege(
                   'kokonut_farm_activity_event_owner', relation_oid,
                   attribute.attname, 'REFERENCES'
               )
           )
    ) THEN
        RAISE EXCEPTION 'farm activity event function owner retains an unexpected column privilege';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS role
         WHERE role.rolname = 'kokonut_runtime'
           AND (role.rolsuper OR role.rolcreatedb OR role.rolcreaterole
                OR role.rolreplication OR role.rolbypassrls OR role.rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_runtime must remain a non-inheriting restricted login or placeholder';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_runtime'
            OR member_role.rolname = 'kokonut_runtime'
    ) THEN
        RAISE EXCEPTION 'kokonut_runtime must not have or lend role memberships';
    END IF;

    SELECT procedure.prosecdef,
           pg_catalog.pg_get_userbyid(procedure.proowner) AS owner_name
      INTO context_accessor
      FROM pg_catalog.pg_proc AS procedure
     WHERE procedure.oid = pg_catalog.to_regprocedure(
         'kokonut_security.current_tenant_context()'
     );
    IF NOT FOUND OR NOT context_accessor.prosecdef
       OR context_accessor.owner_name IS DISTINCT FROM 'kokonut_mobile_context_owner' THEN
        RAISE EXCEPTION 'signed tenant-context accessor must retain its bounded migration-394 owner';
    END IF;

    IF pg_catalog.pg_get_userbyid(
        (SELECT procedure.proowner
           FROM pg_catalog.pg_proc AS procedure
          WHERE procedure.oid = pg_catalog.to_regprocedure(
              'public.record_gateway_farm_activity_create()'
          ))
    ) IS DISTINCT FROM 'kokonut_farm_activity_event_owner'
       OR pg_catalog.pg_get_userbyid(
        (SELECT procedure.proowner
           FROM pg_catalog.pg_proc AS procedure
          WHERE procedure.oid = pg_catalog.to_regprocedure(
              'public.record_farm_activity_gateway_operation()'
          ))
    ) IS DISTINCT FROM 'kokonut_farm_activity_event_owner'
       OR pg_catalog.pg_get_userbyid(
        (SELECT procedure.proowner
           FROM pg_catalog.pg_proc AS procedure
          WHERE procedure.oid = pg_catalog.to_regprocedure(
              'public.guard_farm_activity_operator_event_insert()'
          ))
    ) IS DISTINCT FROM 'kokonut_farm_activity_event_owner' THEN
        RAISE EXCEPTION 'farm activity event trigger functions must retain their bounded owner';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.farm_activity_operator_event
            FROM kokonut_runtime;
        GRANT SELECT ON TABLE public.farm_activity_operator_event
            TO kokonut_runtime;

        -- Table-level REVOKE does not clear independent column grants.
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.farm_activity_operator_event FROM kokonut_runtime',
                column_name
            );
        END LOOP;
    END IF;
END;
$$;

ALTER TABLE public.farm_activity_operator_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.farm_activity_operator_event FORCE ROW LEVEL SECURITY;

-- A permissive relation grant is paired with a restrictive context policy so
-- any later permissive SELECT policy cannot widen visibility beyond the
-- verified operator location. No relation privilege is added to PUBLIC.
DROP POLICY IF EXISTS farm_activity_operator_event_select_roles
    ON public.farm_activity_operator_event;
CREATE POLICY farm_activity_operator_event_select_roles
    ON public.farm_activity_operator_event
    FOR SELECT
    TO PUBLIC
    USING (TRUE);

DROP POLICY IF EXISTS farm_activity_operator_event_signed_location_select
    ON public.farm_activity_operator_event;
CREATE POLICY farm_activity_operator_event_signed_location_select
    ON public.farm_activity_operator_event
    AS RESTRICTIVE
    FOR SELECT
    TO PUBLIC
    USING (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
             WHERE context.actor_type = 'operator'
               AND context.location_id = farm_activity_operator_event.location_id
        )
    );

DROP POLICY IF EXISTS farm_activity_operator_event_owner_insert
    ON public.farm_activity_operator_event;
CREATE POLICY farm_activity_operator_event_owner_insert
    ON public.farm_activity_operator_event
    FOR INSERT
    TO kokonut_farm_activity_event_owner
    WITH CHECK (TRUE);

DROP POLICY IF EXISTS farm_activity_operator_event_signed_location_insert
    ON public.farm_activity_operator_event;
CREATE POLICY farm_activity_operator_event_signed_location_insert
    ON public.farm_activity_operator_event
    AS RESTRICTIVE
    FOR INSERT
    TO PUBLIC
    WITH CHECK (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
             WHERE context.actor_type = 'operator'
               AND context.location_id = farm_activity_operator_event.location_id
               AND context.actor_id = farm_activity_operator_event.actor_operator_id
        )
    );

COMMENT ON TABLE public.farm_activity_operator_event IS
    'Append-only Gateway audit for non-Field-Collector farm activity. Runtime SELECT is filtered by the database-signed operator location context; trigger-owned appends require the matching signed actor and location.';

COMMIT;
