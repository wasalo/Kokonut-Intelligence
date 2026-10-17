-- Isolate event-handler notification creation from the shared application and
-- EventBus control-plane identities. The login remains NOLOGIN until the
-- operator provisions its dedicated password through runtime_role.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_notification_enqueue_owner'
    ) THEN
        CREATE ROLE kokonut_notification_enqueue_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_notification_enqueue_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_notification_enqueue_owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_notification_enqueue_login'
    ) THEN
        CREATE ROLE kokonut_notification_enqueue_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_notification_enqueue_login'
           AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_notification_enqueue_login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN (
                   'kokonut_notification_enqueue_owner',
                   'kokonut_notification_enqueue_login'
               )
            OR member_role.rolname IN (
                   'kokonut_notification_enqueue_owner',
                   'kokonut_notification_enqueue_login'
               )
    ) THEN
        RAISE EXCEPTION 'notification enqueue roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_notification_enqueue_login;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_notification_enqueue_owner;
GRANT USAGE ON SCHEMA public TO kokonut_notification_enqueue_owner;

REVOKE ALL ON public.platform_event FROM kokonut_notification_enqueue_owner;
GRANT SELECT (id, event_type, payload) ON public.platform_event
    TO kokonut_notification_enqueue_owner;
REVOKE ALL ON public.notification_outbox FROM kokonut_notification_enqueue_owner;
GRANT SELECT (id, source_event_id, event_type, channel, destination_key, payload, location_id),
      INSERT (source_event_id, event_type, channel, destination_key, payload, location_id),
      UPDATE (location_id)
    ON public.notification_outbox TO kokonut_notification_enqueue_owner;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class
         WHERE oid = 'public.platform_event'::regclass AND relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'platform_event'
           AND policyname = 'notification_enqueue_owner_read'
    ) THEN
        CREATE POLICY notification_enqueue_owner_read
            ON public.platform_event FOR SELECT
            TO kokonut_notification_enqueue_owner USING (true);
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class
         WHERE oid = 'public.notification_outbox'::regclass AND relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = 'notification_outbox'
               AND policyname = 'notification_enqueue_owner_read'
        ) THEN
            CREATE POLICY notification_enqueue_owner_read
                ON public.notification_outbox FOR SELECT
                TO kokonut_notification_enqueue_owner USING (true);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = 'notification_outbox'
               AND policyname = 'notification_enqueue_owner_insert'
        ) THEN
            CREATE POLICY notification_enqueue_owner_insert
                ON public.notification_outbox FOR INSERT
                TO kokonut_notification_enqueue_owner WITH CHECK (true);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = 'notification_outbox'
               AND policyname = 'notification_enqueue_owner_update'
        ) THEN
            CREATE POLICY notification_enqueue_owner_update
                ON public.notification_outbox FOR UPDATE
                TO kokonut_notification_enqueue_owner
                USING (true) WITH CHECK (true);
        END IF;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.enqueue_notification_intents(
    requested_event_id UUID,
    requested_event_type TEXT,
    requested_location_id UUID,
    requested_intents JSONB
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    source_event RECORD;
    source_location_id UUID;
    intent JSONB;
    intent_channel TEXT;
    intent_destination TEXT;
    intent_payload JSONB;
    intent_key TEXT;
    seen_intents TEXT[] := ARRAY[]::TEXT[];
    inserted_id UUID;
    existing RECORD;
    inserted_count INTEGER := 0;
BEGIN
    IF session_user <> 'kokonut_notification_enqueue_login' THEN
        RAISE EXCEPTION 'notification enqueue requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    IF requested_event_id IS NULL
       OR requested_event_type IS NULL
       OR requested_event_type NOT IN ('data_stale', 'threshold_breached')
       OR requested_intents IS NULL
       OR jsonb_typeof(requested_intents) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'notification enqueue arguments are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF jsonb_array_length(requested_intents) NOT BETWEEN 1 AND 3 THEN
        RAISE EXCEPTION 'notification enqueue arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT event.event_type, event.payload
      INTO source_event
      FROM public.platform_event AS event
     WHERE event.id = requested_event_id;
    IF NOT FOUND OR source_event.event_type <> requested_event_type THEN
        RAISE EXCEPTION 'notification source event is missing or mismatched'
            USING ERRCODE = '22023';
    END IF;

    IF NULLIF(source_event.payload ->> 'location_id', '') IS NOT NULL THEN
        BEGIN
            source_location_id := (source_event.payload ->> 'location_id')::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'notification source location is invalid'
                USING ERRCODE = '22023';
        END;
    END IF;
    IF requested_location_id IS DISTINCT FROM source_location_id THEN
        RAISE EXCEPTION 'notification location does not match its source event'
            USING ERRCODE = '22023';
    END IF;

    FOR intent IN SELECT value FROM jsonb_array_elements(requested_intents)
    LOOP
        IF jsonb_typeof(intent) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'notification intent shape is invalid'
                USING ERRCODE = '22023';
        END IF;
        IF NOT (intent ?& ARRAY['channel', 'destination_key', 'payload'])
           OR (SELECT count(*) FROM jsonb_object_keys(intent)) <> 3 THEN
            RAISE EXCEPTION 'notification intent shape is invalid'
                USING ERRCODE = '22023';
        END IF;
        intent_channel := intent ->> 'channel';
        intent_destination := intent ->> 'destination_key';
        intent_payload := intent -> 'payload';
        IF intent_channel IS NULL
           OR intent_channel NOT IN ('webhook', 'directus', 'email')
           OR intent_destination IS DISTINCT FROM 'primary'
           OR jsonb_typeof(intent_payload) IS DISTINCT FROM 'object'
           OR octet_length(intent_payload::TEXT) > 16384 THEN
            RAISE EXCEPTION 'notification intent content is invalid'
                USING ERRCODE = '22023';
        END IF;
        intent_key := intent_channel || ':' || intent_destination;
        IF intent_key = ANY(seen_intents) THEN
            RAISE EXCEPTION 'notification intent contains a duplicate destination'
                USING ERRCODE = '22023';
        END IF;
        seen_intents := array_append(seen_intents, intent_key);

        INSERT INTO public.notification_outbox (
            source_event_id, event_type, channel, destination_key, payload, location_id
        ) VALUES (
            requested_event_id, requested_event_type, intent_channel,
            intent_destination, intent_payload, requested_location_id
        )
        ON CONFLICT (source_event_id, channel, destination_key) DO NOTHING
        RETURNING id INTO inserted_id;
        IF FOUND THEN
            inserted_count := inserted_count + 1;
            CONTINUE;
        END IF;

        SELECT outbox.event_type, outbox.payload, outbox.location_id
          INTO existing
          FROM public.notification_outbox AS outbox
         WHERE outbox.source_event_id = requested_event_id
           AND outbox.channel = intent_channel
           AND outbox.destination_key = intent_destination
         FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'notification identity disappeared during enqueue'
                USING ERRCODE = '40001';
        END IF;
        IF existing.event_type <> requested_event_type
           OR existing.payload <> intent_payload THEN
            RAISE EXCEPTION 'notification identity conflicts with existing content'
                USING ERRCODE = '23505';
        END IF;
        IF existing.location_id IS NULL AND requested_location_id IS NOT NULL THEN
            UPDATE public.notification_outbox
               SET location_id = requested_location_id
             WHERE source_event_id = requested_event_id
               AND channel = intent_channel
               AND destination_key = intent_destination
               AND location_id IS NULL;
        ELSIF existing.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'notification identity conflicts with source location'
                USING ERRCODE = '23505';
        END IF;
    END LOOP;

    RETURN inserted_count;
END;
$$;

ALTER FUNCTION kokonut_security.enqueue_notification_intents(UUID, TEXT, UUID, JSONB)
    OWNER TO kokonut_notification_enqueue_owner;
REVOKE ALL ON FUNCTION
    kokonut_security.enqueue_notification_intents(UUID, TEXT, UUID, JSONB)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    kokonut_security.enqueue_notification_intents(UUID, TEXT, UUID, JSONB)
    TO kokonut_notification_enqueue_login;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION
            kokonut_security.enqueue_notification_intents(UUID, TEXT, UUID, JSONB)
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION
            kokonut_security.enqueue_notification_intents(UUID, TEXT, UUID, JSONB)
            FROM kokonut_operator_auth;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_execution') THEN
        REVOKE ALL ON FUNCTION
            kokonut_security.enqueue_notification_intents(UUID, TEXT, UUID, JSONB)
            FROM kokonut_worker_execution;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.enqueue_notification_intents(UUID, TEXT, UUID, JSONB) IS
    'Validates and idempotently enqueues bounded notification intents for the two global EventBus notification types; never sends them.';

COMMIT;
