-- Bound EventBus cache invalidation to a signed worker location grant.
-- This migration does not enable application-table RLS or grant table access
-- to kokonut_worker_execution.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_cache_invalidation_owner'
    ) THEN
        CREATE ROLE kokonut_cache_invalidation_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_cache_invalidation_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_cache_invalidation_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_cache_invalidation_owner'
            OR member_role.rolname = 'kokonut_cache_invalidation_owner'
    ) THEN
        RAISE EXCEPTION 'cache invalidation function owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security TO kokonut_cache_invalidation_owner;
GRANT USAGE ON SCHEMA public TO kokonut_cache_invalidation_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_cache_invalidation_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_cache_invalidation_owner;
REVOKE ALL ON public.platform_event, public.cache_entry
    FROM kokonut_cache_invalidation_owner;
GRANT SELECT (id, event_type, payload) ON public.platform_event
    TO kokonut_cache_invalidation_owner;
GRANT SELECT (computation_type, location_id, is_valid) ON public.cache_entry
    TO kokonut_cache_invalidation_owner;
GRANT UPDATE (is_valid, invalidation_reason, invalidated_at) ON public.cache_entry
    TO kokonut_cache_invalidation_owner;

CREATE OR REPLACE FUNCTION kokonut_security.invalidate_worker_computation_cache(
    requested_event_id UUID,
    requested_event_type TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    source_event RECORD;
    target_computation_type TEXT;
    invalidation_count INTEGER;
BEGIN
    SELECT scope.tenant_id, scope.location_id, scope.actor_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope(
          'computation_cache', 'invalidate'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed cache invalidation scope is required'
            USING ERRCODE = '42501';
    END IF;

    IF requested_event_id IS NULL THEN
        RAISE EXCEPTION 'event ID is required'
            USING ERRCODE = '42501';
    END IF;

    target_computation_type := CASE requested_event_type
        WHEN 'metric_computed' THEN 'analytics'
        WHEN 'crisp_scored' THEN 'crisp'
        ELSE NULL
    END;
    IF target_computation_type IS NULL THEN
        RAISE EXCEPTION 'event type is not allowed for cache invalidation'
            USING ERRCODE = '42501';
    END IF;

    SELECT event.event_type, event.payload ->> 'location_id' AS location_id
      INTO source_event
      FROM public.platform_event AS event
     WHERE event.id = requested_event_id;
    IF NOT FOUND
       OR source_event.event_type IS DISTINCT FROM requested_event_type
       OR LOWER(source_event.location_id)
            IS DISTINCT FROM worker_scope.location_id::TEXT THEN
        RAISE EXCEPTION 'event does not match the signed cache invalidation scope'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.cache_entry AS cache
       SET is_valid = FALSE,
           invalidation_reason = requested_event_type || ':' || requested_event_type,
           invalidated_at = statement_timestamp()
     WHERE cache.is_valid IS TRUE
       AND cache.location_id = worker_scope.location_id
       AND cache.computation_type = target_computation_type;
    GET DIAGNOSTICS invalidation_count = ROW_COUNT;
    RETURN invalidation_count;
END;
$$;

ALTER FUNCTION kokonut_security.invalidate_worker_computation_cache(UUID, TEXT)
    OWNER TO kokonut_cache_invalidation_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_cache_invalidation_owner;
REVOKE ALL ON FUNCTION kokonut_security.invalidate_worker_computation_cache(
    UUID, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.invalidate_worker_computation_cache(
    UUID, TEXT
) TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'platform_event'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'platform_event'
          AND policyname = 'cache_invalidation_owner_event_select'
    ) THEN
        CREATE POLICY cache_invalidation_owner_event_select
            ON public.platform_event FOR SELECT
            TO kokonut_cache_invalidation_owner
            USING (
                LOWER(payload ->> 'location_id') = (
                    SELECT scope.location_id::TEXT
                      FROM kokonut_security.current_worker_scope(
                          'computation_cache', 'invalidate'
                      ) AS scope
                )
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'cache_entry'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = 'cache_entry'
              AND policyname = 'cache_invalidation_owner_select'
        ) THEN
            CREATE POLICY cache_invalidation_owner_select
                ON public.cache_entry FOR SELECT
                TO kokonut_cache_invalidation_owner
                USING (location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'computation_cache', 'invalidate'
                      ) AS scope
                ));
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = 'cache_entry'
              AND policyname = 'cache_invalidation_owner_update'
        ) THEN
            CREATE POLICY cache_invalidation_owner_update
                ON public.cache_entry FOR UPDATE
                TO kokonut_cache_invalidation_owner
                USING (location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'computation_cache', 'invalidate'
                      ) AS scope
                ))
                WITH CHECK (location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'computation_cache', 'invalidate'
                      ) AS scope
                ));
        END IF;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.invalidate_worker_computation_cache(UUID, TEXT) IS
    'Invalidates the allowlisted cache type for one matching event and signed worker location.';

COMMIT;
