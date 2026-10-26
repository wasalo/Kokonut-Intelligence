-- Isolate global EventBus claims and receipts from the shared runtime identity.
-- Publishing remains in the caller's transaction; operator replay and cleanup
-- remain on their existing reviewed paths.
BEGIN;

ALTER TABLE public.platform_event
    ADD COLUMN IF NOT EXISTS lease_token UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_event_dispatch_owner'
    ) THEN
        CREATE ROLE kokonut_event_dispatch_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_event_dispatch_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'event-dispatch function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_event_dispatch_login'
    ) THEN
        CREATE ROLE kokonut_event_dispatch_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_event_dispatch_login'
           AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'event-dispatch login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN (
                   'kokonut_event_dispatch_owner', 'kokonut_event_dispatch_login'
               )
            OR member_role.rolname IN (
                   'kokonut_event_dispatch_owner', 'kokonut_event_dispatch_login'
               )
    ) THEN
        RAISE EXCEPTION 'event-dispatch roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO kokonut_event_dispatch_owner;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_event_dispatch_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_event_dispatch_owner;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_event_dispatch_login;
REVOKE CREATE ON SCHEMA public FROM kokonut_event_dispatch_login;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_event_dispatch_login;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_event_dispatch_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_event_dispatch_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_event_dispatch_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_event_dispatch_login;

GRANT SELECT (id, event_type, payload, priority, status, created_at, retry_count,
              max_retries, lease_owner, lease_token, lease_expires_at)
    ON public.platform_event TO kokonut_event_dispatch_owner;
GRANT UPDATE (status, claimed_at, worker_id, retry_count, error_message,
              processed_at, lease_owner, lease_token, lease_expires_at)
    ON public.platform_event TO kokonut_event_dispatch_owner;
GRANT SELECT (id, event_type, module_path, function_name, is_enabled,
              priority_order, timeout_seconds)
    ON public.event_handler TO kokonut_event_dispatch_owner;
GRANT SELECT (event_id, handler_id, status, attempt_count)
    ON public.event_handler_delivery TO kokonut_event_dispatch_owner;
GRANT INSERT (event_id, handler_id, status, attempt_count, started_at, updated_at),
      UPDATE (status, attempt_count, started_at, completed_at, last_error, updated_at)
    ON public.event_handler_delivery TO kokonut_event_dispatch_owner;
GRANT INSERT (event_id, handler_id, status, duration_ms, error_message)
    ON public.event_handler_log TO kokonut_event_dispatch_owner;
GRANT SELECT (original_event_id, disposition)
    ON public.event_dead_letter TO kokonut_event_dispatch_owner;
GRANT SELECT (failure_count, last_error)
    ON public.event_dead_letter TO kokonut_event_dispatch_owner;
GRANT INSERT (original_event_id, event_type, payload, failure_count, last_error),
      UPDATE (failure_count, last_error)
    ON public.event_dead_letter TO kokonut_event_dispatch_owner;

DO $$
DECLARE relation_name TEXT;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'platform_event', 'event_handler', 'event_handler_delivery',
        'event_handler_log', 'event_dead_letter'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_class
             WHERE oid = format('public.%I', relation_name)::regclass
               AND relrowsecurity
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = relation_name
               AND policyname = 'event_dispatch_owner_access'
        ) THEN
            EXECUTE format(
                'CREATE POLICY event_dispatch_owner_access ON public.%I '
                'FOR ALL TO kokonut_event_dispatch_owner USING (true) WITH CHECK (true)',
                relation_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.claim_platform_event_batch(
    requested_worker_id TEXT,
    requested_limit INTEGER,
    requested_lease_seconds INTEGER
)
RETURNS TABLE (
    id UUID, event_type VARCHAR, payload JSONB, retry_count INTEGER,
    max_retries INTEGER, lease_token UUID
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_event_dispatch_login'
       OR requested_worker_id IS NULL
       OR requested_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
       OR requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 100
       OR requested_lease_seconds IS NULL
       OR requested_lease_seconds NOT BETWEEN 30 AND 3600 THEN
        RAISE EXCEPTION 'event claim is not authorized' USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    WITH claimable AS (
        SELECT event.id
          FROM public.platform_event AS event
         WHERE event.status = 'pending'
            OR (event.status = 'processing' AND event.lease_expires_at < NOW())
         ORDER BY CASE event.priority
                      WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                      WHEN 'normal' THEN 2 ELSE 3 END,
                  event.created_at, event.id
         LIMIT requested_limit
         FOR UPDATE SKIP LOCKED
    ), claimed AS (
        UPDATE public.platform_event AS event
           SET status = 'processing', claimed_at = NOW(), worker_id = requested_worker_id,
               lease_owner = requested_worker_id, lease_token = gen_random_uuid(),
               lease_expires_at = NOW() + make_interval(secs => requested_lease_seconds)
          FROM claimable
         WHERE event.id = claimable.id
        RETURNING event.id, event.event_type, event.payload, event.retry_count,
                  event.max_retries, event.lease_token
    )
    SELECT claimed.id, claimed.event_type, claimed.payload, claimed.retry_count,
           claimed.max_retries, claimed.lease_token
      FROM claimed;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_platform_event_handlers(
    requested_event_id UUID,
    requested_event_type TEXT,
    requested_worker_id TEXT,
    requested_lease_token UUID
)
RETURNS TABLE (
    handler_id UUID, module_path VARCHAR, function_name VARCHAR,
    timeout_seconds INTEGER, delivery_status VARCHAR
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_event_dispatch_login'
       OR requested_event_id IS NULL OR requested_lease_token IS NULL
       OR requested_event_type IS NULL
       OR requested_worker_id IS NULL
       OR NOT EXISTS (
           SELECT 1 FROM public.platform_event AS event
            WHERE event.id = requested_event_id
              AND event.event_type = requested_event_type
              AND event.status = 'processing'
              AND event.lease_owner = requested_worker_id
              AND event.lease_token = requested_lease_token
              AND event.lease_expires_at > NOW()
       ) THEN
        RAISE EXCEPTION 'event handler lookup is not authorized' USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.event_handler AS handler
         WHERE handler.event_type = requested_event_type
           AND handler.is_enabled = TRUE
           AND handler.timeout_seconds NOT BETWEEN 1 AND 3570
    ) THEN
        RAISE EXCEPTION 'enabled event handler timeout is outside the worker bound';
    END IF;

    RETURN QUERY
    SELECT handler.id, handler.module_path, handler.function_name,
           handler.timeout_seconds, delivery.status
      FROM public.event_handler AS handler
      LEFT JOIN public.event_handler_delivery AS delivery
        ON delivery.event_id = requested_event_id
       AND delivery.handler_id = handler.id
     WHERE handler.event_type = requested_event_type
       AND handler.is_enabled = TRUE
     ORDER BY handler.priority_order, handler.id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.renew_platform_event_lease(
    requested_event_id UUID,
    requested_worker_id TEXT,
    requested_lease_token UUID,
    requested_lease_seconds INTEGER
)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE changed INTEGER;
BEGIN
    IF session_user <> 'kokonut_event_dispatch_login'
       OR requested_event_id IS NULL OR requested_lease_token IS NULL
       OR requested_worker_id IS NULL
       OR requested_lease_seconds IS NULL
       OR requested_lease_seconds NOT BETWEEN 30 AND 3600 THEN
        RAISE EXCEPTION 'event lease renewal is not authorized' USING ERRCODE = '42501';
    END IF;

    UPDATE public.platform_event AS event
       SET lease_expires_at = NOW() + make_interval(secs => requested_lease_seconds)
     WHERE event.id = requested_event_id
       AND event.status = 'processing'
       AND event.lease_owner = requested_worker_id
       AND event.lease_token = requested_lease_token
       AND event.lease_expires_at > NOW();
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.begin_platform_event_handler(
    requested_event_id UUID,
    requested_handler_id UUID,
    requested_worker_id TEXT,
    requested_lease_token UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE changed INTEGER;
BEGIN
    IF session_user <> 'kokonut_event_dispatch_login'
       OR requested_event_id IS NULL OR requested_handler_id IS NULL
       OR requested_lease_token IS NULL OR requested_worker_id IS NULL THEN
        RAISE EXCEPTION 'event handler start is not authorized' USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.event_handler_delivery (
        event_id, handler_id, status, attempt_count, started_at, updated_at
    )
    SELECT event.id, handler.id, 'processing', 1, NOW(), NOW()
      FROM public.platform_event AS event
      JOIN public.event_handler AS handler
        ON handler.id = requested_handler_id
       AND handler.event_type = event.event_type
       AND handler.is_enabled = TRUE
     WHERE event.id = requested_event_id
       AND event.status = 'processing'
       AND event.lease_owner = requested_worker_id
       AND event.lease_token = requested_lease_token
       AND event.lease_expires_at > NOW()
       AND handler.timeout_seconds BETWEEN 1 AND 3570
    ON CONFLICT (event_id, handler_id) DO UPDATE
       SET status = 'processing',
           attempt_count = public.event_handler_delivery.attempt_count + 1,
           started_at = NOW(), completed_at = NULL, updated_at = NOW(), last_error = NULL
     WHERE public.event_handler_delivery.status <> 'success';
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.finish_platform_event_handler(
    requested_event_id UUID,
    requested_handler_id UUID,
    requested_worker_id TEXT,
    requested_lease_token UUID,
    requested_status TEXT,
    requested_duration_ms INTEGER,
    requested_error TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE changed INTEGER;
BEGIN
    IF session_user <> 'kokonut_event_dispatch_login'
       OR requested_event_id IS NULL OR requested_handler_id IS NULL
       OR requested_lease_token IS NULL OR requested_worker_id IS NULL
       OR requested_status IS NULL
       OR requested_status NOT IN ('success', 'error', 'timeout')
       OR requested_duration_ms IS NULL OR requested_duration_ms < 0
       OR requested_duration_ms > 86400000
       OR (requested_status = 'success' AND requested_error IS NOT NULL)
       OR (requested_status <> 'success' AND (
           requested_error IS NULL OR length(requested_error) NOT BETWEEN 1 AND 500
           OR requested_error ~ '[[:cntrl:]]'
       )) THEN
        RAISE EXCEPTION 'event handler completion is not authorized' USING ERRCODE = '42501';
    END IF;

    UPDATE public.event_handler_delivery AS delivery
       SET status = requested_status,
           completed_at = NOW(),
           last_error = requested_error,
           updated_at = NOW()
      FROM public.platform_event AS event
     WHERE delivery.event_id = requested_event_id
       AND delivery.handler_id = requested_handler_id
       AND delivery.status = 'processing'
       AND event.id = delivery.event_id
       AND event.status = 'processing'
       AND event.lease_owner = requested_worker_id
       AND event.lease_token = requested_lease_token
       AND event.lease_expires_at > NOW();
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 1 THEN
        RETURN FALSE;
    END IF;

    INSERT INTO public.event_handler_log (
        event_id, handler_id, status, duration_ms, error_message
    ) VALUES (
        requested_event_id, requested_handler_id, requested_status,
        requested_duration_ms, requested_error
    );
    RETURN TRUE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.complete_platform_event(
    requested_event_id UUID,
    requested_worker_id TEXT,
    requested_lease_token UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE changed INTEGER;
BEGIN
    IF session_user <> 'kokonut_event_dispatch_login'
       OR requested_event_id IS NULL OR requested_lease_token IS NULL
       OR requested_worker_id IS NULL THEN
        RAISE EXCEPTION 'event completion is not authorized' USING ERRCODE = '42501';
    END IF;

    UPDATE public.platform_event AS event
       SET status = 'completed', processed_at = NOW(),
           lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL
     WHERE event.id = requested_event_id
       AND event.status = 'processing'
       AND event.lease_owner = requested_worker_id
       AND event.lease_token = requested_lease_token
       AND event.lease_expires_at > NOW()
       AND NOT EXISTS (
           SELECT 1
             FROM public.event_handler AS handler
             LEFT JOIN public.event_handler_delivery AS delivery
               ON delivery.event_id = event.id
              AND delivery.handler_id = handler.id
            WHERE handler.event_type = event.event_type
              AND handler.is_enabled = TRUE
              AND delivery.status IS DISTINCT FROM 'success'
       );
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.retry_platform_event(
    requested_event_id UUID,
    requested_worker_id TEXT,
    requested_lease_token UUID,
    requested_retry_count INTEGER,
    requested_max_retries INTEGER
)
RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE event_row RECORD;
DECLARE final_status TEXT;
BEGIN
    IF session_user <> 'kokonut_event_dispatch_login'
       OR requested_event_id IS NULL OR requested_lease_token IS NULL
       OR requested_worker_id IS NULL
       OR requested_retry_count IS NULL OR requested_retry_count < 1
       OR requested_max_retries IS NULL OR requested_max_retries < 0 THEN
        RAISE EXCEPTION 'event retry is not authorized' USING ERRCODE = '42501';
    END IF;

    SELECT event.event_type, event.payload, event.retry_count, event.max_retries
      INTO event_row
      FROM public.platform_event AS event
     WHERE event.id = requested_event_id
       AND event.status = 'processing'
       AND event.lease_owner = requested_worker_id
       AND event.lease_token = requested_lease_token
       AND event.lease_expires_at > NOW()
       AND event.retry_count + 1 = requested_retry_count
       AND event.max_retries = requested_max_retries
       AND EXISTS (
           SELECT 1
             FROM public.event_handler_delivery AS delivery
            WHERE delivery.event_id = event.id
              AND delivery.status IN ('error', 'timeout')
       )
     FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'lease_lost';
    END IF;

    final_status := CASE
        WHEN requested_retry_count >= requested_max_retries THEN 'dead_letter'
        ELSE 'pending'
    END;
    UPDATE public.platform_event AS event
       SET status = final_status,
           retry_count = requested_retry_count,
           error_message = CASE
               WHEN final_status = 'dead_letter' THEN 'Max retries exceeded'
               ELSE 'One or more handlers failed'
           END,
           lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL
     WHERE event.id = requested_event_id;

    IF final_status = 'dead_letter' THEN
        INSERT INTO public.event_dead_letter (
            original_event_id, event_type, payload, failure_count, last_error
        ) VALUES (
            requested_event_id, event_row.event_type, event_row.payload,
            requested_retry_count, 'Max retries exceeded'
        )
        ON CONFLICT (original_event_id) WHERE disposition = 'pending'
        DO UPDATE SET failure_count = EXCLUDED.failure_count,
                      last_error = EXCLUDED.last_error;
    END IF;
    RETURN final_status;
END;
$$;

ALTER FUNCTION kokonut_security.claim_platform_event_batch(TEXT, INTEGER, INTEGER)
    OWNER TO kokonut_event_dispatch_owner;
ALTER FUNCTION kokonut_security.list_platform_event_handlers(UUID, TEXT, TEXT, UUID)
    OWNER TO kokonut_event_dispatch_owner;
ALTER FUNCTION kokonut_security.renew_platform_event_lease(UUID, TEXT, UUID, INTEGER)
    OWNER TO kokonut_event_dispatch_owner;
ALTER FUNCTION kokonut_security.begin_platform_event_handler(UUID, UUID, TEXT, UUID)
    OWNER TO kokonut_event_dispatch_owner;
ALTER FUNCTION kokonut_security.finish_platform_event_handler(UUID, UUID, TEXT, UUID, TEXT, INTEGER, TEXT)
    OWNER TO kokonut_event_dispatch_owner;
ALTER FUNCTION kokonut_security.complete_platform_event(UUID, TEXT, UUID)
    OWNER TO kokonut_event_dispatch_owner;
ALTER FUNCTION kokonut_security.retry_platform_event(UUID, TEXT, UUID, INTEGER, INTEGER)
    OWNER TO kokonut_event_dispatch_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_event_dispatch_owner;

REVOKE ALL ON FUNCTION kokonut_security.claim_platform_event_batch(TEXT, INTEGER, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_platform_event_handlers(UUID, TEXT, TEXT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.renew_platform_event_lease(UUID, TEXT, UUID, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.begin_platform_event_handler(UUID, UUID, TEXT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.finish_platform_event_handler(UUID, UUID, TEXT, UUID, TEXT, INTEGER, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.complete_platform_event(UUID, TEXT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.retry_platform_event(UUID, TEXT, UUID, INTEGER, INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.claim_platform_event_batch(TEXT, INTEGER, INTEGER)
    TO kokonut_event_dispatch_login;
GRANT EXECUTE ON FUNCTION kokonut_security.list_platform_event_handlers(UUID, TEXT, TEXT, UUID)
    TO kokonut_event_dispatch_login;
GRANT EXECUTE ON FUNCTION kokonut_security.renew_platform_event_lease(UUID, TEXT, UUID, INTEGER)
    TO kokonut_event_dispatch_login;
GRANT EXECUTE ON FUNCTION kokonut_security.begin_platform_event_handler(UUID, UUID, TEXT, UUID)
    TO kokonut_event_dispatch_login;
GRANT EXECUTE ON FUNCTION kokonut_security.finish_platform_event_handler(UUID, UUID, TEXT, UUID, TEXT, INTEGER, TEXT)
    TO kokonut_event_dispatch_login;
GRANT EXECUTE ON FUNCTION kokonut_security.complete_platform_event(UUID, TEXT, UUID)
    TO kokonut_event_dispatch_login;
GRANT EXECUTE ON FUNCTION kokonut_security.retry_platform_event(UUID, TEXT, UUID, INTEGER, INTEGER)
    TO kokonut_event_dispatch_login;

COMMIT;
