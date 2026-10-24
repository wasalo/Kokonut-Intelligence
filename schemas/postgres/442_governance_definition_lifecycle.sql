-- Route governance circle and role status changes through audited Gateway actions.

BEGIN;

CREATE TABLE IF NOT EXISTS public.governance_definition_action_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('circle', 'role')),
    entity_id UUID NOT NULL,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('submit', 'approve', 'reject', 'activate', 'suspend', 'retire')),
    prior_status TEXT NOT NULL,
    resulting_status TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (
        NULLIF(BTRIM(reason), '') IS NOT NULL AND CHAR_LENGTH(reason) <= 2000
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id),
    CHECK (
        (entity_type = 'circle' AND (
            (action = 'submit' AND prior_status = 'draft' AND resulting_status = 'submitted')
            OR (action = 'reject' AND prior_status IN ('draft', 'submitted') AND resulting_status = 'rejected')
            OR (action = 'activate' AND prior_status = 'submitted' AND resulting_status = 'active')
            OR (action = 'suspend' AND prior_status = 'active' AND resulting_status = 'suspended')
            OR (action = 'retire' AND prior_status IN ('active', 'suspended') AND resulting_status = 'retired')
        )) OR (entity_type = 'role' AND (
            (action = 'submit' AND prior_status = 'draft' AND resulting_status = 'submitted')
            OR (action = 'approve' AND prior_status = 'submitted' AND resulting_status = 'approved')
            OR (action = 'reject' AND prior_status IN ('draft', 'submitted') AND resulting_status = 'rejected')
            OR (action = 'activate' AND prior_status = 'approved' AND resulting_status = 'active')
            OR (action = 'suspend' AND prior_status = 'active' AND resulting_status = 'suspended')
            OR (action = 'retire' AND prior_status IN ('active', 'suspended') AND resulting_status = 'retired')
        ))
    )
);

CREATE INDEX IF NOT EXISTS idx_governance_definition_action_location
    ON public.governance_definition_action_event(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_governance_definition_action_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'governance definition action history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_definition_action_immutable
    ON public.governance_definition_action_event;
CREATE TRIGGER trg_governance_definition_action_immutable
    BEFORE UPDATE OR DELETE ON public.governance_definition_action_event
    FOR EACH ROW EXECUTE FUNCTION public.prevent_governance_definition_action_mutation();

CREATE OR REPLACE FUNCTION public.guard_governance_definition_status()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status IS DISTINCT FROM 'draft'
           AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles
                 WHERE rolname = current_user AND rolsuper
           ) THEN
            RAISE EXCEPTION 'governance definitions must be created as drafts';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status
       AND current_user <> 'kokonut_governance_action_owner'
       AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = current_user AND rolsuper
       ) THEN
        RAISE EXCEPTION 'governance definition status requires the audited Gateway lifecycle';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_circle_status_guard ON public.governance_circle;
CREATE TRIGGER trg_governance_circle_status_guard
    BEFORE INSERT OR UPDATE OF status ON public.governance_circle
    FOR EACH ROW EXECUTE FUNCTION public.guard_governance_definition_status();

DROP TRIGGER IF EXISTS trg_governance_role_status_guard ON public.governance_role;
CREATE TRIGGER trg_governance_role_status_guard
    BEFORE INSERT OR UPDATE OF status ON public.governance_role
    FOR EACH ROW EXECUTE FUNCTION public.guard_governance_definition_status();

REVOKE ALL ON TABLE public.governance_definition_action_event FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE public.governance_definition_action_event
    TO kokonut_governance_action_owner;
GRANT SELECT ON TABLE public.governance_circle, public.governance_role,
    public.governance_role_assignment, public.operator_governance_party_binding,
    public.operator_identity, public.party, public.operator_scope_grant
    TO kokonut_governance_action_owner;
GRANT USAGE, CREATE ON SCHEMA kokonut_security TO kokonut_governance_action_owner;
GRANT UPDATE (status, retired_at) ON TABLE public.governance_circle
    TO kokonut_governance_action_owner;
GRANT UPDATE (status) ON TABLE public.governance_role
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_governance_action_owner;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE public.governance_definition_action_event FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.governance_definition_action_event FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.transition_governance_definition(
    requested_location_id UUID,
    requested_entity_type TEXT,
    requested_entity_id UUID,
    requested_request_id UUID,
    requested_action TEXT,
    requested_reason TEXT
)
RETURNS TABLE (
    event_id UUID,
    entity_type TEXT,
    entity_id UUID,
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
    prior_event public.governance_definition_action_event%ROWTYPE;
    prior_state TEXT;
    next_state TEXT;
    creator_party UUID;
    row_found BOOLEAN := FALSE;
    new_event_id UUID;
    event_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'governance definition action requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_entity_type IS NULL
       OR requested_entity_type NOT IN ('circle', 'role')
       OR requested_entity_id IS NULL
       OR requested_request_id IS NULL
       OR requested_action IS NULL
       OR requested_action NOT IN ('submit', 'approve', 'reject', 'activate', 'suspend', 'retire')
       OR requested_reason IS NULL
       OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 2000
       OR (requested_entity_type = 'circle' AND requested_action = 'approve') THEN
        RAISE EXCEPTION 'governance definition action arguments are invalid' USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_roles', requested_action, requested_location_id
    ) THEN
        RAISE EXCEPTION 'governance definition action requires an active exact location grant'
            USING ERRCODE = '42501';
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
        RAISE EXCEPTION 'governance definition action requires an active person binding'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 442)
    );
    SELECT event.* INTO prior_event
      FROM public.governance_definition_action_event AS event
     WHERE event.operator_id = context_record.actor_id
       AND event.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_event.location_id IS DISTINCT FROM requested_location_id
           OR prior_event.entity_type IS DISTINCT FROM requested_entity_type
           OR prior_event.entity_id IS DISTINCT FROM requested_entity_id
           OR prior_event.action IS DISTINCT FROM requested_action
           OR prior_event.reason IS DISTINCT FROM BTRIM(requested_reason) THEN
            RAISE EXCEPTION 'governance definition request ID was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        IF prior_event.actor_party_id IS DISTINCT FROM actor_party THEN
            RAISE EXCEPTION 'governance definition retry is not from its recorded actor binding'
                USING ERRCODE = '42501';
        END IF;
        event_id := prior_event.id;
        entity_type := prior_event.entity_type;
        entity_id := prior_event.entity_id;
        action := prior_event.action;
        prior_status := prior_event.prior_status;
        resulting_status := prior_event.resulting_status;
        actor_party_id := prior_event.actor_party_id;
        created_at := prior_event.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    IF requested_entity_type = 'circle' THEN
        SELECT circle.status, circle.created_by_party_id
          INTO prior_state, creator_party
          FROM public.governance_circle AS circle
         WHERE circle.id = requested_entity_id
           AND circle.scope_type = 'location'
           AND circle.scope_id = requested_location_id
         FOR UPDATE;
        row_found := FOUND;
        IF row_found THEN
            next_state := CASE
                WHEN requested_action = 'submit' AND prior_state = 'draft' THEN 'submitted'
                WHEN requested_action = 'reject' AND prior_state IN ('draft', 'submitted') THEN 'rejected'
                WHEN requested_action = 'activate' AND prior_state = 'submitted' THEN 'active'
                WHEN requested_action = 'suspend' AND prior_state = 'active' THEN 'suspended'
                WHEN requested_action = 'retire' AND prior_state IN ('active', 'suspended') THEN 'retired'
                ELSE NULL
            END;
        END IF;
    ELSE
        SELECT role.status, role.created_by_party_id
          INTO prior_state, creator_party
          FROM public.governance_role AS role
          JOIN public.governance_circle AS circle ON circle.id = role.circle_id
         WHERE role.id = requested_entity_id
           AND circle.scope_type = 'location'
           AND circle.scope_id = requested_location_id
         FOR UPDATE OF role;
        row_found := FOUND;
        IF row_found THEN
            next_state := CASE
                WHEN requested_action = 'submit' AND prior_state = 'draft' THEN 'submitted'
                WHEN requested_action = 'approve' AND prior_state = 'submitted' THEN 'approved'
                WHEN requested_action = 'reject' AND prior_state IN ('draft', 'submitted') THEN 'rejected'
                WHEN requested_action = 'activate' AND prior_state = 'approved' THEN 'active'
                WHEN requested_action = 'suspend' AND prior_state = 'active' THEN 'suspended'
                WHEN requested_action = 'retire' AND prior_state IN ('active', 'suspended') THEN 'retired'
                ELSE NULL
            END;
        END IF;
    END IF;
    IF NOT row_found THEN
        RAISE EXCEPTION 'governance definition was not found in this location' USING ERRCODE = 'P0002';
    END IF;
    IF next_state IS NULL THEN
        RAISE EXCEPTION 'governance definition transition is unavailable from its current state'
            USING ERRCODE = '55000';
    END IF;
    IF requested_action IN ('approve', 'activate', 'reject')
       AND creator_party IS NOT NULL
       AND creator_party = actor_party THEN
        RAISE EXCEPTION 'governance definition review requires a different bound person'
            USING ERRCODE = '42501';
    END IF;

    IF requested_entity_type = 'role' AND requested_action = 'activate'
       AND NOT EXISTS (
            SELECT 1 FROM public.governance_role AS role
            JOIN public.governance_circle AS circle ON circle.id = role.circle_id
            WHERE role.id = requested_entity_id AND circle.status = 'active'
       ) THEN
        RAISE EXCEPTION 'a governance role can only activate inside an active circle'
            USING ERRCODE = '55000';
    END IF;

    IF requested_action IN ('suspend', 'retire') AND EXISTS (
        SELECT 1
          FROM public.governance_role_assignment AS assignment
          JOIN public.governance_role AS role ON role.id = assignment.role_id
          JOIN public.governance_circle AS circle ON circle.id = role.circle_id
         WHERE assignment.status IN ('proposed', 'active', 'suspended')
           AND ((requested_entity_type = 'role' AND role.id = requested_entity_id)
             OR (requested_entity_type = 'circle' AND circle.id = requested_entity_id))
    ) THEN
        RAISE EXCEPTION 'resolve role assignments before suspending or retiring governance authority'
            USING ERRCODE = '55000';
    END IF;
    IF requested_entity_type = 'circle' AND requested_action = 'retire'
       AND EXISTS (
            SELECT 1 FROM public.governance_role AS role
             WHERE role.circle_id = requested_entity_id
               AND role.status NOT IN ('retired', 'rejected')
       ) THEN
        RAISE EXCEPTION 'retire or reject circle roles before retiring their circle'
            USING ERRCODE = '55000';
    END IF;

    IF requested_entity_type = 'circle' THEN
        UPDATE public.governance_circle
           SET status = next_state,
               retired_at = CASE WHEN next_state = 'retired' THEN clock_timestamp() ELSE retired_at END
         WHERE id = requested_entity_id;
    ELSE
        UPDATE public.governance_role SET status = next_state
         WHERE id = requested_entity_id;
    END IF;

    INSERT INTO public.governance_definition_action_event (
        operator_id, request_id, location_id, entity_type, entity_id, actor_party_id,
        action, prior_status, resulting_status, reason
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_entity_type, requested_entity_id, actor_party, requested_action,
        prior_state, next_state, BTRIM(requested_reason)
    ) RETURNING id, public.governance_definition_action_event.created_at
      INTO new_event_id, event_time;

    event_id := new_event_id;
    entity_type := requested_entity_type;
    entity_id := requested_entity_id;
    action := requested_action;
    prior_status := prior_state;
    resulting_status := next_state;
    actor_party_id := actor_party;
    created_at := event_time;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.transition_governance_definition(UUID, TEXT, UUID, UUID, TEXT, TEXT)
    OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.transition_governance_definition(UUID, TEXT, UUID, UUID, TEXT, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.transition_governance_definition(UUID, TEXT, UUID, UUID, TEXT, TEXT)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.transition_governance_definition(UUID, TEXT, UUID, UUID, TEXT, TEXT)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_governance_action_owner;

COMMENT ON TABLE public.governance_definition_action_event IS
    'Append-only operator, person, reason, and request history for governance circle and role lifecycle actions.';
COMMENT ON FUNCTION kokonut_security.transition_governance_definition(UUID, TEXT, UUID, UUID, TEXT, TEXT) IS
    'Applies an exact-grant, signed-location governance circle or role lifecycle transition and records its immutable actor history.';

COMMIT;
