-- Govern location-scoped tactical item transitions through the Gateway.

BEGIN;

CREATE TABLE IF NOT EXISTS public.governance_tactical_action_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES public.governance_tactical_item(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('start', 'dispose', 'cancel')),
    prior_status TEXT NOT NULL CHECK (prior_status IN ('open', 'in_progress')),
    resulting_status TEXT NOT NULL CHECK (resulting_status IN ('in_progress', 'disposed', 'cancelled')),
    reason TEXT NOT NULL CHECK (NULLIF(BTRIM(reason), '') IS NOT NULL AND CHAR_LENGTH(reason) <= 2000),
    disposition_type TEXT CHECK (disposition_type IN (
        'next_action', 'delegate', 'create_work_item', 'create_proposal',
        'escalate', 'defer', 'no_action'
    )),
    disposition_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id),
    CHECK (
        (action = 'start' AND prior_status = 'open' AND resulting_status = 'in_progress'
            AND disposition_type IS NULL AND disposition_summary IS NULL)
        OR (action = 'dispose' AND prior_status = 'in_progress' AND resulting_status = 'disposed'
            AND disposition_type IS NOT NULL AND NULLIF(BTRIM(disposition_summary), '') IS NOT NULL
            AND CHAR_LENGTH(disposition_summary) <= 4000)
        OR (action = 'cancel' AND prior_status IN ('open', 'in_progress')
            AND resulting_status = 'cancelled' AND disposition_type IS NULL
            AND disposition_summary IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_governance_tactical_action_event_location
    ON public.governance_tactical_action_event(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_governance_tactical_action_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'governance tactical action history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_tactical_action_event_immutable
    ON public.governance_tactical_action_event;
CREATE TRIGGER trg_governance_tactical_action_event_immutable
    BEFORE UPDATE OR DELETE ON public.governance_tactical_action_event
    FOR EACH ROW EXECUTE FUNCTION public.prevent_governance_tactical_action_event_mutation();

REVOKE ALL ON TABLE public.governance_tactical_action_event FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE public.governance_tactical_action_event
    TO kokonut_governance_action_owner;
GRANT SELECT ON TABLE public.governance_tactical_item,
    public.governance_tactical_session, public.governance_circle,
    public.governance_role, public.governance_role_assignment,
    public.operator_governance_party_binding, public.party,
    public.operator_identity, public.operator_scope_grant
    TO kokonut_governance_action_owner;
GRANT UPDATE (status, disposition_type, disposition_summary,
    disposed_by_party_id, disposed_at, updated_at)
    ON TABLE public.governance_tactical_item TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_governance_action_owner;

REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_tactical_item FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_tactical_item FROM kokonut_runtime;
        REVOKE ALL ON TABLE public.governance_tactical_action_event FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_tactical_item FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.governance_tactical_action_event FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.transition_governance_tactical_item(
    requested_location_id UUID,
    requested_item_id UUID,
    requested_request_id UUID,
    requested_action TEXT,
    requested_reason TEXT,
    requested_disposition_type TEXT DEFAULT NULL,
    requested_disposition_summary TEXT DEFAULT NULL
)
RETURNS TABLE (
    event_id UUID,
    item_id UUID,
    action TEXT,
    prior_status TEXT,
    resulting_status TEXT,
    actor_party_id UUID,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party UUID;
    prior_event public.governance_tactical_action_event%ROWTYPE;
    item_record RECORD;
    next_status TEXT;
    normalized_reason TEXT;
    normalized_summary TEXT;
    new_event_id UUID;
    event_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'tactical action requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF requested_action IS NULL OR requested_action NOT IN ('start', 'dispose', 'cancel')
       OR requested_item_id IS NULL OR requested_request_id IS NULL
       OR requested_location_id IS NULL
       OR requested_reason IS NULL
       OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 2000
       OR (requested_action = 'dispose' AND (
            requested_disposition_type IS NULL OR requested_disposition_type NOT IN (
                'next_action', 'delegate', 'create_work_item', 'create_proposal',
                'escalate', 'defer', 'no_action'
            ) OR requested_disposition_summary IS NULL
            OR NULLIF(BTRIM(requested_disposition_summary), '') IS NULL
            OR CHAR_LENGTH(requested_disposition_summary) > 4000
       ))
       OR (requested_action <> 'dispose' AND (
            requested_disposition_type IS NOT NULL
            OR requested_disposition_summary IS NOT NULL
       )) THEN
        RAISE EXCEPTION 'tactical action arguments are invalid' USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_tactical', requested_action, requested_location_id
    ) THEN
        RAISE EXCEPTION 'tactical action requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_reason := BTRIM(requested_reason);
    normalized_summary := NULLIF(BTRIM(requested_disposition_summary), '');

    SELECT binding.party_id INTO actor_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS person
        ON person.id = binding.party_id
       AND person.party_type = 'person'
       AND person.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF actor_party IS NULL THEN
        RAISE EXCEPTION 'tactical action requires an active person binding'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 441)
    );
    SELECT event.* INTO prior_event
      FROM public.governance_tactical_action_event AS event
     WHERE event.operator_id = context_record.actor_id
       AND event.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_event.location_id IS DISTINCT FROM requested_location_id
           OR prior_event.item_id IS DISTINCT FROM requested_item_id
           OR prior_event.action IS DISTINCT FROM requested_action
           OR prior_event.reason IS DISTINCT FROM normalized_reason
           OR prior_event.disposition_type IS DISTINCT FROM requested_disposition_type
           OR prior_event.disposition_summary IS DISTINCT FROM normalized_summary THEN
            RAISE EXCEPTION 'tactical action request ID was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        IF prior_event.actor_party_id IS DISTINCT FROM actor_party THEN
            RAISE EXCEPTION 'tactical action retry is not from the recorded actor binding'
                USING ERRCODE = '42501';
        END IF;
        event_id := prior_event.id;
        item_id := prior_event.item_id;
        action := prior_event.action;
        prior_status := prior_event.prior_status;
        resulting_status := prior_event.resulting_status;
        actor_party_id := prior_event.actor_party_id;
        created_at := prior_event.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT tactical.status, tactical.owner_role_id, tactical.owner_party_id,
           session.status AS session_status, circle.status AS circle_status
      INTO item_record
      FROM public.governance_tactical_item AS tactical
      JOIN public.governance_tactical_session AS session ON session.id = tactical.session_id
      JOIN public.governance_circle AS circle ON circle.id = session.circle_id
     WHERE tactical.id = requested_item_id
       AND circle.scope_type = 'location'
       AND circle.scope_id = requested_location_id
     FOR UPDATE OF tactical;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'tactical item was not found' USING ERRCODE = 'P0002';
    END IF;
    IF item_record.circle_status <> 'active'
       OR item_record.session_status = 'cancelled' THEN
        RAISE EXCEPTION 'tactical item is in a cancelled session or inactive circle'
            USING ERRCODE = '55000';
    END IF;

    IF requested_action = 'start' THEN
        IF item_record.status <> 'open' THEN
            RAISE EXCEPTION 'only an open tactical item can be started' USING ERRCODE = '55000';
        END IF;
        IF item_record.owner_party_id IS DISTINCT FROM actor_party
           AND NOT EXISTS (
                SELECT 1
                  FROM public.governance_role_assignment AS assignment
                  JOIN public.governance_role AS role ON role.id = assignment.role_id
                  JOIN public.governance_circle AS owner_circle
                    ON owner_circle.id = role.circle_id
                 WHERE role.id = item_record.owner_role_id
                   AND role.status = 'active'
                   AND owner_circle.status = 'active'
                   AND owner_circle.scope_type = 'location'
                   AND owner_circle.scope_id = requested_location_id
                   AND assignment.party_id = actor_party
                   AND assignment.status = 'active'
                   AND assignment.recusal_status <> 'recused'
                   AND assignment.effective_from <= clock_timestamp()
                   AND (assignment.effective_until IS NULL
                        OR assignment.effective_until >= clock_timestamp())
           ) THEN
            RAISE EXCEPTION 'only the assigned person or active role holder can start this item'
                USING ERRCODE = '42501';
        END IF;
        next_status := 'in_progress';
        UPDATE public.governance_tactical_item AS tactical
           SET status = next_status, updated_at = clock_timestamp()
         WHERE tactical.id = requested_item_id;
    ELSIF requested_action = 'dispose' THEN
        IF item_record.status <> 'in_progress' THEN
            RAISE EXCEPTION 'only an in-progress tactical item can be disposed' USING ERRCODE = '55000';
        END IF;
        next_status := 'disposed';
        UPDATE public.governance_tactical_item AS tactical
           SET status = next_status,
               disposition_type = requested_disposition_type,
               disposition_summary = normalized_summary,
               disposed_by_party_id = actor_party,
               disposed_at = clock_timestamp(),
               updated_at = clock_timestamp()
         WHERE tactical.id = requested_item_id;
    ELSE
        IF item_record.status NOT IN ('open', 'in_progress') THEN
            RAISE EXCEPTION 'only an open or in-progress tactical item can be cancelled' USING ERRCODE = '55000';
        END IF;
        next_status := 'cancelled';
        UPDATE public.governance_tactical_item AS tactical
           SET status = next_status, updated_at = clock_timestamp()
         WHERE tactical.id = requested_item_id;
    END IF;

    INSERT INTO public.governance_tactical_action_event (
        operator_id, request_id, location_id, item_id, actor_party_id, action,
        prior_status, resulting_status, reason, disposition_type, disposition_summary
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_item_id, actor_party, requested_action, item_record.status,
        next_status, normalized_reason, requested_disposition_type, normalized_summary
    ) RETURNING id, public.governance_tactical_action_event.created_at
         INTO new_event_id, event_time;

    event_id := new_event_id;
    item_id := requested_item_id;
    action := requested_action;
    prior_status := item_record.status;
    resulting_status := next_status;
    actor_party_id := actor_party;
    created_at := event_time;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.transition_governance_tactical_item(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT
) OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.transition_governance_tactical_item(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.transition_governance_tactical_item(
            UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.transition_governance_tactical_item(
            UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.governance_tactical_action_event IS
    'Append-only actor, reason, and idempotency history for Gateway tactical item transitions.';
COMMENT ON FUNCTION kokonut_security.transition_governance_tactical_item(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT
) IS 'Applies one signed, exact-grant, location-scoped tactical item lifecycle transition.';

COMMIT;
