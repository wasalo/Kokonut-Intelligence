-- Create location-scoped tactical sessions through an audited Gateway function.

BEGIN;

CREATE TABLE IF NOT EXISTS public.governance_tactical_session_creation_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    session_id UUID NOT NULL REFERENCES public.governance_tactical_session(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    requested_content JSONB NOT NULL CHECK (jsonb_typeof(requested_content) = 'object'),
    reason TEXT NOT NULL CHECK (
        NULLIF(BTRIM(reason), '') IS NOT NULL AND CHAR_LENGTH(reason) <= 2000
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

CREATE INDEX IF NOT EXISTS idx_governance_tactical_session_creation_location
    ON public.governance_tactical_session_creation_event(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_governance_tactical_session_creation_event_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'governance tactical session creation history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_tactical_session_creation_event_immutable
    ON public.governance_tactical_session_creation_event;
CREATE TRIGGER trg_governance_tactical_session_creation_event_immutable
    BEFORE UPDATE OR DELETE ON public.governance_tactical_session_creation_event
    FOR EACH ROW EXECUTE FUNCTION public.prevent_governance_tactical_session_creation_event_change();

CREATE OR REPLACE FUNCTION public.guard_governance_tactical_session_create()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF current_user <> 'kokonut_governance_action_owner'
       AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = current_user AND rolsuper
       ) THEN
        RAISE EXCEPTION 'tactical sessions require the audited Gateway creation path'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_tactical_session_create_guard
    ON public.governance_tactical_session;
CREATE TRIGGER trg_governance_tactical_session_create_guard
    BEFORE INSERT ON public.governance_tactical_session
    FOR EACH ROW EXECUTE FUNCTION public.guard_governance_tactical_session_create();

REVOKE ALL ON FUNCTION public.prevent_governance_tactical_session_creation_event_change() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.guard_governance_tactical_session_create() FROM PUBLIC;
REVOKE ALL ON TABLE public.governance_tactical_session_creation_event FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE public.governance_tactical_session_creation_event
    TO kokonut_governance_action_owner;
GRANT SELECT ON TABLE public.governance_tactical_session, public.governance_circle,
    public.governance_role, public.operator_governance_party_binding,
    public.operator_identity, public.party, public.operator_scope_grant
    TO kokonut_governance_action_owner;
GRANT INSERT (
    id, circle_id, session_type, title, scheduled_at, facilitator_role_id,
    recorder_role_id, status, agenda_scope, created_by_party_id
) ON TABLE public.governance_tactical_session TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_governance_action_owner;

DO $$
BEGIN
    REVOKE INSERT ON TABLE public.governance_tactical_session FROM PUBLIC;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE INSERT ON TABLE public.governance_tactical_session FROM kokonut_runtime;
        REVOKE ALL ON TABLE public.governance_tactical_session_creation_event FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE INSERT ON TABLE public.governance_tactical_session FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.governance_tactical_session_creation_event FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.create_governance_tactical_session(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_content JSONB,
    requested_reason TEXT
)
RETURNS TABLE (
    event_id UUID,
    session_id UUID,
    actor_party_id UUID,
    status TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party UUID;
    prior_event public.governance_tactical_session_creation_event%ROWTYPE;
    requested_circle_id UUID;
    facilitator_role UUID;
    recorder_role UUID;
    requested_schedule TIMESTAMPTZ;
    new_session_id UUID;
    new_event_id UUID;
    event_time TIMESTAMPTZ;
    session_status TEXT := 'planned';
    allowed_keys TEXT[] := ARRAY[
        'circle_id', 'session_type', 'title', 'scheduled_at',
        'facilitator_role_id', 'recorder_role_id', 'agenda_scope'
    ];
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'tactical session creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_request_id IS NULL
       OR requested_content IS NULL
       OR jsonb_typeof(requested_content) IS DISTINCT FROM 'object'
       OR requested_reason IS NULL
       OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 2000 THEN
        RAISE EXCEPTION 'tactical session creation arguments are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_tactical', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'tactical session creation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_object_keys(requested_content) AS content_key
         WHERE NOT (content_key = ANY(allowed_keys))
    ) OR NOT (requested_content ?& ARRAY['circle_id', 'session_type', 'title']) THEN
        RAISE EXCEPTION 'tactical session content has missing or unsupported fields'
            USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(requested_content -> 'circle_id') IS DISTINCT FROM 'string'
       OR jsonb_typeof(requested_content -> 'session_type') IS DISTINCT FROM 'string'
       OR jsonb_typeof(requested_content -> 'title') IS DISTINCT FROM 'string'
       OR NULLIF(BTRIM(requested_content ->> 'title'), '') IS NULL
       OR CHAR_LENGTH(requested_content ->> 'title') > 255
       OR requested_content ->> 'session_type' NOT IN (
            'weekly_review', 'stakeholder_health', 'relationship_review',
            'risk_triage', 'governance_followup'
       ) THEN
        RAISE EXCEPTION 'tactical session title or type is invalid' USING ERRCODE = '22023';
    END IF;
    BEGIN
        requested_circle_id := (requested_content ->> 'circle_id')::UUID;
    EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'tactical session circle identifier is invalid' USING ERRCODE = '22023';
    END;

    IF requested_content ? 'scheduled_at' AND requested_content -> 'scheduled_at' <> 'null'::jsonb THEN
        IF jsonb_typeof(requested_content -> 'scheduled_at') IS DISTINCT FROM 'string' THEN
            RAISE EXCEPTION 'scheduled_at must be an ISO timestamp or null' USING ERRCODE = '22023';
        END IF;
        IF requested_content ->> 'scheduled_at' !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
            RAISE EXCEPTION 'scheduled_at must include an explicit timezone' USING ERRCODE = '22023';
        END IF;
        BEGIN
            requested_schedule := (requested_content ->> 'scheduled_at')::TIMESTAMPTZ;
        EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
            RAISE EXCEPTION 'scheduled_at must be a valid ISO timestamp' USING ERRCODE = '22023';
        END;
    END IF;
    IF requested_content ? 'agenda_scope'
       AND requested_content -> 'agenda_scope' <> 'null'::jsonb
       AND (jsonb_typeof(requested_content -> 'agenda_scope') IS DISTINCT FROM 'string'
         OR CHAR_LENGTH(requested_content ->> 'agenda_scope') > 10000) THEN
        RAISE EXCEPTION 'agenda_scope must be text up to 10000 characters or null' USING ERRCODE = '22023';
    END IF;
    IF requested_content ? 'facilitator_role_id'
       AND requested_content -> 'facilitator_role_id' <> 'null'::jsonb THEN
        IF jsonb_typeof(requested_content -> 'facilitator_role_id') IS DISTINCT FROM 'string' THEN
            RAISE EXCEPTION 'facilitator_role_id must be a UUID or null' USING ERRCODE = '22023';
        END IF;
        BEGIN
            facilitator_role := (requested_content ->> 'facilitator_role_id')::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'facilitator_role_id must be a UUID or null' USING ERRCODE = '22023';
        END;
    END IF;
    IF requested_content ? 'recorder_role_id'
       AND requested_content -> 'recorder_role_id' <> 'null'::jsonb THEN
        IF jsonb_typeof(requested_content -> 'recorder_role_id') IS DISTINCT FROM 'string' THEN
            RAISE EXCEPTION 'recorder_role_id must be a UUID or null' USING ERRCODE = '22023';
        END IF;
        BEGIN
            recorder_role := (requested_content ->> 'recorder_role_id')::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'recorder_role_id must be a UUID or null' USING ERRCODE = '22023';
        END;
    END IF;

    SELECT binding.party_id INTO actor_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS person
        ON person.id = binding.party_id
       AND person.party_type = 'person'
       AND person.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF actor_party IS NULL THEN
        RAISE EXCEPTION 'tactical session creation requires an active person binding'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 444)
    );
    SELECT event.* INTO prior_event
      FROM public.governance_tactical_session_creation_event AS event
     WHERE event.operator_id = context_record.actor_id
       AND event.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_event.location_id IS DISTINCT FROM requested_location_id
           OR prior_event.requested_content IS DISTINCT FROM requested_content
           OR prior_event.reason IS DISTINCT FROM BTRIM(requested_reason) THEN
            RAISE EXCEPTION 'tactical session request ID was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        IF prior_event.actor_party_id IS DISTINCT FROM actor_party THEN
            RAISE EXCEPTION 'tactical session retry is not from its recorded actor binding'
                USING ERRCODE = '42501';
        END IF;
        event_id := prior_event.id;
        session_id := prior_event.session_id;
        actor_party_id := prior_event.actor_party_id;
        status := 'planned';
        created_at := prior_event.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    PERFORM circle.id
      FROM public.governance_circle AS circle
     WHERE circle.id = requested_circle_id
       AND circle.scope_type = 'location'
       AND circle.scope_id = requested_location_id
       AND circle.status = 'active'
     FOR SHARE OF circle;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'tactical session circle must be active in this location'
            USING ERRCODE = 'P0002';
    END IF;
    IF facilitator_role IS NOT NULL THEN
        PERFORM role.id
          FROM public.governance_role AS role
         WHERE role.id = facilitator_role
           AND role.circle_id = requested_circle_id
           AND role.status = 'active'
         FOR SHARE OF role;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'facilitator role must be active in the selected circle'
                USING ERRCODE = 'P0002';
        END IF;
    END IF;
    IF recorder_role IS NOT NULL THEN
        PERFORM role.id
          FROM public.governance_role AS role
         WHERE role.id = recorder_role
           AND role.circle_id = requested_circle_id
           AND role.status = 'active'
         FOR SHARE OF role;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'recorder role must be active in the selected circle'
                USING ERRCODE = 'P0002';
        END IF;
    END IF;

    new_session_id := gen_random_uuid();
    INSERT INTO public.governance_tactical_session (
        id, circle_id, session_type, title, scheduled_at,
        facilitator_role_id, recorder_role_id, status, agenda_scope, created_by_party_id
    ) VALUES (
        new_session_id, requested_circle_id, requested_content ->> 'session_type',
        BTRIM(requested_content ->> 'title'), requested_schedule,
        facilitator_role, recorder_role, session_status,
        NULLIF(requested_content ->> 'agenda_scope', ''), actor_party
    );
    INSERT INTO public.governance_tactical_session_creation_event (
        operator_id, request_id, location_id, session_id, actor_party_id,
        requested_content, reason
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        new_session_id, actor_party, requested_content, BTRIM(requested_reason)
    ) RETURNING id, public.governance_tactical_session_creation_event.created_at
      INTO new_event_id, event_time;

    event_id := new_event_id;
    session_id := new_session_id;
    actor_party_id := actor_party;
    status := session_status;
    created_at := event_time;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.create_governance_tactical_session(UUID, UUID, JSONB, TEXT)
    OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_governance_tactical_session(UUID, UUID, JSONB, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.create_governance_tactical_session(UUID, UUID, JSONB, TEXT)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_governance_tactical_session(UUID, UUID, JSONB, TEXT)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_governance_action_owner;

COMMENT ON TABLE public.governance_tactical_session_creation_event IS
    'Private append-only actor, reason, request, and idempotency history for Gateway tactical session creation.';
COMMENT ON FUNCTION kokonut_security.create_governance_tactical_session(UUID, UUID, JSONB, TEXT) IS
    'Creates a planned tactical session in an active location circle with exact signed grant, active person binding, and immutable request history.';

COMMIT;
