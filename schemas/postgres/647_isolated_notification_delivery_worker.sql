-- Isolate durable notification claims and acknowledgements from the shared
-- EventBus/runtime PostgreSQL identities. Operator stats and dead-letter
-- replay/disposition remain on the existing reviewed operator CLI.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_notification_delivery_owner'
    ) THEN
        CREATE ROLE kokonut_notification_delivery_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_notification_delivery_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'notification-delivery function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_notification_delivery_login'
    ) THEN
        CREATE ROLE kokonut_notification_delivery_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_notification_delivery_login'
           AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'notification-delivery login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN (
                   'kokonut_notification_delivery_owner',
                   'kokonut_notification_delivery_login'
               )
            OR member_role.rolname IN (
                   'kokonut_notification_delivery_owner',
                   'kokonut_notification_delivery_login'
               )
    ) THEN
        RAISE EXCEPTION 'notification-delivery roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_notification_delivery_login;
REVOKE ALL ON TABLE public.notification_outbox,
    public.notification_outbox_attempt FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO kokonut_notification_delivery_owner;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_notification_delivery_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_notification_delivery_owner;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_notification_delivery_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_notification_delivery_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_notification_delivery_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_notification_delivery_login;
REVOKE CREATE ON SCHEMA public FROM kokonut_notification_delivery_login;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_notification_delivery_login;

GRANT SELECT (
    id, source_event_id, event_type, channel, destination_key, payload, status, attempt_count,
    retry_cycle_attempts, available_at, lease_owner, lease_token,
    lease_expires_at, last_error_class, created_at, delivered_at, updated_at
) ON public.notification_outbox TO kokonut_notification_delivery_owner;
GRANT UPDATE (
    status, retry_cycle_attempts, available_at, lease_owner, lease_token,
    lease_expires_at, last_error_class, updated_at, delivered_at
) ON public.notification_outbox TO kokonut_notification_delivery_owner;
-- PostgreSQL requires table-level UPDATE for SELECT ... FOR UPDATE. This
-- non-login owner is reachable only through the fixed SECURITY DEFINER API.
GRANT UPDATE ON public.notification_outbox TO kokonut_notification_delivery_owner;
GRANT SELECT (outbox_id, attempt_number, lease_owner, lease_token, status, error_class),
      INSERT (outbox_id, attempt_number, lease_owner, lease_token),
      UPDATE (status, error_class, finished_at)
    ON public.notification_outbox_attempt
    TO kokonut_notification_delivery_owner;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class
         WHERE oid = 'public.notification_outbox'::regclass AND relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public'
           AND tablename = 'notification_outbox'
           AND policyname = 'notification_delivery_owner_access'
    ) THEN
        CREATE POLICY notification_delivery_owner_access
            ON public.notification_outbox FOR ALL
            TO kokonut_notification_delivery_owner
            USING (true) WITH CHECK (true);
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class
         WHERE oid = 'public.notification_outbox_attempt'::regclass AND relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public'
           AND tablename = 'notification_outbox_attempt'
           AND policyname = 'notification_delivery_owner_access'
    ) THEN
        CREATE POLICY notification_delivery_owner_access
            ON public.notification_outbox_attempt FOR ALL
            TO kokonut_notification_delivery_owner
            USING (true) WITH CHECK (true);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.claim_notification_outbox_batch(
    requested_worker_id TEXT,
    requested_limit INTEGER,
    requested_lease_seconds INTEGER,
    requested_channels TEXT[]
)
RETURNS TABLE (
    id UUID, source_event_id UUID, event_type VARCHAR, channel VARCHAR,
    destination_key VARCHAR, payload JSONB, attempt_count INTEGER,
    lease_owner VARCHAR, lease_token UUID
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE expired_row RECORD;
DECLARE claimed_row RECORD;
DECLARE claimed_attempt_count INTEGER;
DECLARE claimed_lease_token UUID;
BEGIN
    IF session_user <> 'kokonut_notification_delivery_login'
       OR requested_worker_id IS NULL
       OR requested_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,149}$'
       OR requested_limit IS NULL OR requested_limit < 1 OR requested_limit > 100
       OR requested_lease_seconds IS NULL
       OR requested_lease_seconds < 30 OR requested_lease_seconds > 3600
       OR requested_channels IS NULL
       OR cardinality(requested_channels) > 3
       OR EXISTS (
           SELECT 1 FROM unnest(requested_channels) AS configured(channel_name)
            WHERE configured.channel_name IS NULL
               OR configured.channel_name NOT IN ('webhook', 'directus', 'email')
       ) THEN
        RAISE EXCEPTION 'notification claim is not authorized' USING ERRCODE = '42501';
    END IF;

    FOR expired_row IN
        SELECT outbox.id, outbox.lease_token
          FROM public.notification_outbox AS outbox
         WHERE outbox.status = 'processing'
           AND outbox.lease_expires_at < NOW()
         ORDER BY outbox.lease_expires_at, outbox.id
         LIMIT requested_limit
         FOR UPDATE SKIP LOCKED
    LOOP
        UPDATE public.notification_outbox_attempt AS attempt
           SET status = 'lease_lost', finished_at = NOW(),
               error_class = COALESCE(attempt.error_class, 'LeaseExpired')
         WHERE attempt.outbox_id = expired_row.id
           AND attempt.lease_token = expired_row.lease_token
           AND attempt.status = 'processing';

        UPDATE public.notification_outbox AS outbox
           SET status = CASE
                   WHEN outbox.retry_cycle_attempts >= 8 THEN 'dead_letter'
                   ELSE 'retryable'
               END,
               lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
               available_at = NOW(), updated_at = NOW(),
               last_error_class = COALESCE(outbox.last_error_class, 'LeaseExpired')
         WHERE outbox.id = expired_row.id
           AND outbox.status = 'processing'
           AND outbox.lease_token = expired_row.lease_token;
    END LOOP;

    FOR claimed_row IN
        SELECT outbox.id, outbox.source_event_id, outbox.event_type, outbox.channel,
               outbox.destination_key, outbox.payload, outbox.attempt_count
          FROM public.notification_outbox AS outbox
         WHERE outbox.status IN ('pending', 'retryable')
           AND outbox.available_at <= NOW()
           AND outbox.channel = ANY(requested_channels)
         ORDER BY outbox.available_at, outbox.created_at, outbox.id
         LIMIT requested_limit
         FOR UPDATE SKIP LOCKED
    LOOP
        UPDATE public.notification_outbox AS outbox
           SET status = 'processing',
               attempt_count = outbox.attempt_count + 1,
               retry_cycle_attempts = outbox.retry_cycle_attempts + 1,
               lease_owner = requested_worker_id,
               lease_token = gen_random_uuid(),
               lease_expires_at = NOW() + make_interval(secs => requested_lease_seconds),
               updated_at = NOW()
         WHERE outbox.id = claimed_row.id
         RETURNING outbox.lease_token, outbox.attempt_count
              INTO claimed_lease_token, claimed_attempt_count;

        INSERT INTO public.notification_outbox_attempt (
            outbox_id, attempt_number, lease_owner, lease_token
        ) VALUES (
            claimed_row.id, claimed_attempt_count,
            requested_worker_id, claimed_lease_token
        );

        id := claimed_row.id;
        source_event_id := claimed_row.source_event_id;
        event_type := claimed_row.event_type;
        channel := claimed_row.channel;
        destination_key := claimed_row.destination_key;
        payload := claimed_row.payload;
        attempt_count := claimed_attempt_count;
        lease_owner := requested_worker_id;
        lease_token := claimed_lease_token;
        RETURN NEXT;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.finish_notification_outbox_attempt(
    requested_id UUID,
    requested_worker_id TEXT,
    requested_lease_token UUID,
    requested_attempt_number INTEGER,
    requested_success BOOLEAN,
    requested_error_class TEXT,
    requested_retry_delay_seconds INTEGER
)
RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE outbox_changed INTEGER;
DECLARE attempt_changed INTEGER;
DECLARE final_status TEXT;
BEGIN
    IF session_user <> 'kokonut_notification_delivery_login'
       OR requested_id IS NULL OR requested_lease_token IS NULL
       OR requested_worker_id IS NULL
       OR requested_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,149}$'
       OR requested_attempt_number IS NULL OR requested_attempt_number < 1
       OR requested_success IS NULL
       OR requested_retry_delay_seconds IS NULL
       OR requested_retry_delay_seconds < 0 OR requested_retry_delay_seconds > 3600
       OR (requested_success AND requested_error_class IS NOT NULL)
       OR (NOT requested_success AND (
           requested_error_class IS NULL
           OR length(requested_error_class) NOT BETWEEN 1 AND 100
           OR requested_error_class !~ '^[A-Za-z0-9_.-]+$'
       )) THEN
        RAISE EXCEPTION 'notification completion is not authorized' USING ERRCODE = '42501';
    END IF;

    UPDATE public.notification_outbox AS outbox
       SET status = CASE
               WHEN requested_success THEN 'succeeded'
               WHEN outbox.retry_cycle_attempts >= 8 THEN 'dead_letter'
               ELSE 'retryable'
           END,
           available_at = CASE
               WHEN requested_success THEN outbox.available_at
               ELSE NOW() + make_interval(secs => requested_retry_delay_seconds)
           END,
           delivered_at = CASE
               WHEN requested_success THEN NOW()
               ELSE outbox.delivered_at
           END,
           last_error_class = requested_error_class,
           lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
           updated_at = NOW()
     WHERE outbox.id = requested_id
       AND outbox.status = 'processing'
       AND outbox.lease_owner = requested_worker_id
       AND outbox.lease_token = requested_lease_token
       AND outbox.lease_expires_at > NOW();
    GET DIAGNOSTICS outbox_changed = ROW_COUNT;

    final_status := CASE
        WHEN outbox_changed <> 1 THEN 'lease_lost'
        WHEN requested_success THEN 'succeeded'
        ELSE 'failed'
    END;

    UPDATE public.notification_outbox_attempt AS attempt
       SET status = final_status,
           error_class = requested_error_class,
           finished_at = NOW()
     WHERE attempt.outbox_id = requested_id
       AND attempt.attempt_number = requested_attempt_number
       AND attempt.lease_owner = requested_worker_id
       AND attempt.lease_token = requested_lease_token
       AND attempt.status = 'processing';
    GET DIAGNOSTICS attempt_changed = ROW_COUNT;

    IF outbox_changed = 1 AND attempt_changed <> 1 THEN
        RAISE EXCEPTION 'notification attempt receipt is missing';
    END IF;

    RETURN final_status;
END;
$$;

ALTER FUNCTION kokonut_security.claim_notification_outbox_batch(TEXT, INTEGER, INTEGER, TEXT[])
    OWNER TO kokonut_notification_delivery_owner;
ALTER FUNCTION kokonut_security.finish_notification_outbox_attempt(
    UUID, TEXT, UUID, INTEGER, BOOLEAN, TEXT, INTEGER
) OWNER TO kokonut_notification_delivery_owner;
REVOKE ALL ON FUNCTION kokonut_security.claim_notification_outbox_batch(
    TEXT, INTEGER, INTEGER, TEXT[]
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.finish_notification_outbox_attempt(
    UUID, TEXT, UUID, INTEGER, BOOLEAN, TEXT, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.claim_notification_outbox_batch(
    TEXT, INTEGER, INTEGER, TEXT[]
) TO kokonut_notification_delivery_login;
GRANT EXECUTE ON FUNCTION kokonut_security.finish_notification_outbox_attempt(
    UUID, TEXT, UUID, INTEGER, BOOLEAN, TEXT, INTEGER
) TO kokonut_notification_delivery_login;

COMMIT;
