-- Complete the Gateway-owned tactical content path for sessions and items.

BEGIN;

CREATE TABLE IF NOT EXISTS public.governance_tactical_content_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    session_id UUID REFERENCES public.governance_tactical_session(id) ON DELETE RESTRICT,
    item_id UUID REFERENCES public.governance_tactical_item(id) ON DELETE RESTRICT,
    operation TEXT NOT NULL CHECK (operation IN ('create_item', 'update_item', 'update_session')),
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    requested_content JSONB NOT NULL CHECK (jsonb_typeof(requested_content) = 'object'),
    prior_content JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(prior_content) = 'object'),
    reason TEXT NOT NULL CHECK (
        NULLIF(BTRIM(reason), '') IS NOT NULL AND CHAR_LENGTH(reason) <= 2000
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id),
    CHECK (
        (operation = 'update_session' AND session_id IS NOT NULL AND item_id IS NULL)
        OR (operation = 'create_item' AND session_id IS NOT NULL AND item_id IS NOT NULL)
        OR (operation = 'update_item' AND session_id IS NOT NULL AND item_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_governance_tactical_content_event_location
    ON public.governance_tactical_content_event(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_governance_tactical_content_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'governance tactical content history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_tactical_content_event_immutable
    ON public.governance_tactical_content_event;
CREATE TRIGGER trg_governance_tactical_content_event_immutable
    BEFORE UPDATE OR DELETE ON public.governance_tactical_content_event
    FOR EACH ROW EXECUTE FUNCTION public.prevent_governance_tactical_content_event_mutation();

CREATE OR REPLACE FUNCTION public.guard_governance_tactical_content_mutation()
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
        RAISE EXCEPTION 'tactical content requires the audited Gateway mutation path'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_tactical_session_content_guard
    ON public.governance_tactical_session;
CREATE TRIGGER trg_governance_tactical_session_content_guard
    BEFORE UPDATE ON public.governance_tactical_session
    FOR EACH ROW EXECUTE FUNCTION public.guard_governance_tactical_content_mutation();

DROP TRIGGER IF EXISTS trg_governance_tactical_item_content_guard
    ON public.governance_tactical_item;
CREATE TRIGGER trg_governance_tactical_item_content_guard
    BEFORE INSERT OR UPDATE ON public.governance_tactical_item
    FOR EACH ROW EXECUTE FUNCTION public.guard_governance_tactical_content_mutation();

REVOKE ALL ON FUNCTION public.prevent_governance_tactical_content_event_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.guard_governance_tactical_content_mutation() FROM PUBLIC;
REVOKE ALL ON TABLE public.governance_tactical_content_event FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE public.governance_tactical_content_event
    TO kokonut_governance_action_owner;
GRANT SELECT ON TABLE public.governance_tactical_session,
    public.governance_tactical_item, public.governance_circle, public.governance_role,
    public.governance_tension, public.work_item, public.stakeholder_decision,
    public.operator_governance_party_binding, public.operator_identity,
    public.operator_scope_grant, public.party
    TO kokonut_governance_action_owner;
-- PostgreSQL requires UPDATE privilege to acquire row locks through SELECT ... FOR SHARE.
-- Grant only the immutable primary-key column for the referenced rows the function locks;
-- the no-login owner cannot change other content through these narrowly-scoped grants.
GRANT UPDATE (id) ON TABLE public.governance_circle, public.governance_role,
    public.governance_tension, public.work_item, public.stakeholder_decision,
    public.operator_governance_party_binding, public.party
    TO kokonut_governance_action_owner;
GRANT INSERT (
    id, session_id, tension_id, work_item_id, decision_id, proposer_party_id,
    owner_role_id, owner_party_id, requested_next_action, priority, due_at, status
) ON TABLE public.governance_tactical_item TO kokonut_governance_action_owner;
GRANT UPDATE (
    tension_id, work_item_id, decision_id, owner_role_id, owner_party_id,
    requested_next_action, priority, due_at, updated_at
) ON TABLE public.governance_tactical_item TO kokonut_governance_action_owner;
GRANT UPDATE (
    session_type, title, scheduled_at, facilitator_role_id,
    recorder_role_id, agenda_scope, updated_at
) ON TABLE public.governance_tactical_session TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_governance_action_owner;

REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_tactical_item FROM PUBLIC;
REVOKE UPDATE ON TABLE public.governance_tactical_session FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_tactical_item FROM kokonut_runtime;
        REVOKE UPDATE ON TABLE public.governance_tactical_session FROM kokonut_runtime;
        REVOKE ALL ON TABLE public.governance_tactical_content_event FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_tactical_item FROM kokonut_directus_runtime;
        REVOKE UPDATE ON TABLE public.governance_tactical_session FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.governance_tactical_content_event FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.mutate_governance_tactical_content(
    requested_location_id UUID,
    requested_operation TEXT,
    requested_target_id UUID,
    requested_request_id UUID,
    requested_content JSONB,
    requested_reason TEXT
)
RETURNS TABLE (
    event_id UUID,
    operation TEXT,
    session_id UUID,
    item_id UUID,
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
    prior_event public.governance_tactical_content_event%ROWTYPE;
    item_record RECORD;
    session_record RECORD;
    requested_session_id UUID;
    requested_tension_id UUID;
    requested_work_item_id UUID;
    requested_decision_id UUID;
    requested_owner_role_id UUID;
    requested_owner_party_id UUID;
    requested_facilitator_role_id UUID;
    requested_recorder_role_id UUID;
    requested_schedule TIMESTAMPTZ;
    requested_due TIMESTAMPTZ;
    tactical_session_id UUID;
    tactical_circle_id UUID;
    tactical_session_status TEXT;
    tactical_circle_status TEXT;
    next_session_type TEXT;
    next_title TEXT;
    next_agenda_scope TEXT;
    next_action TEXT;
    next_priority SMALLINT;
    normalized_reason TEXT;
    normalized_content JSONB;
    prior_content JSONB := '{}'::jsonb;
    allowed_keys TEXT[];
    required_keys TEXT[];
    required_action TEXT;
    new_item_id UUID;
    event_time TIMESTAMPTZ;
    new_event_id UUID;
    reference_id UUID;
BEGIN
    IF requested_operation = 'create_item' THEN
        required_action := 'create';
        allowed_keys := ARRAY[
            'session_id', 'requested_next_action', 'tension_id', 'work_item_id',
            'decision_id', 'owner_role_id', 'owner_party_id', 'priority', 'due_at'
        ];
        required_keys := ARRAY['session_id', 'requested_next_action'];
    ELSIF requested_operation = 'update_item' THEN
        required_action := 'update';
        allowed_keys := ARRAY[
            'requested_next_action', 'tension_id', 'work_item_id', 'decision_id',
            'owner_role_id', 'owner_party_id', 'priority', 'due_at'
        ];
        required_keys := ARRAY[]::text[];
    ELSIF requested_operation = 'update_session' THEN
        required_action := 'update';
        allowed_keys := ARRAY[
            'session_type', 'title', 'scheduled_at', 'facilitator_role_id',
            'recorder_role_id', 'agenda_scope'
        ];
        required_keys := ARRAY[]::text[];
    ELSE
        RAISE EXCEPTION 'tactical content operation is invalid' USING ERRCODE = '22023';
    END IF;

    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'tactical content mutation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL OR requested_request_id IS NULL
       OR requested_content IS NULL
       OR jsonb_typeof(requested_content) IS DISTINCT FROM 'object'
       OR requested_reason IS NULL
       OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 2000
       OR (requested_operation = 'create_item' AND requested_target_id IS NOT NULL)
       OR (requested_operation <> 'create_item' AND requested_target_id IS NULL) THEN
        RAISE EXCEPTION 'tactical content mutation arguments are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_object_keys(requested_content) AS content_key
         WHERE NOT (content_key = ANY(allowed_keys))
    ) OR NOT (requested_content ?& required_keys)
       OR (requested_operation <> 'create_item' AND requested_content = '{}'::jsonb) THEN
        RAISE EXCEPTION 'tactical content has missing or unsupported fields'
            USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_tactical', required_action, requested_location_id
    ) THEN
        RAISE EXCEPTION 'tactical content mutation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO actor_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS person
        ON person.id = binding.party_id
       AND person.party_type = 'person'
       AND person.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, person;
    IF actor_party IS NULL THEN
        RAISE EXCEPTION 'tactical content mutation requires an active person binding'
            USING ERRCODE = '42501';
    END IF;

    normalized_reason := BTRIM(requested_reason);
    normalized_content := requested_content;
    IF requested_content ? 'requested_next_action' THEN
        IF jsonb_typeof(requested_content -> 'requested_next_action') IS DISTINCT FROM 'string'
           OR NULLIF(BTRIM(requested_content ->> 'requested_next_action'), '') IS NULL
           OR CHAR_LENGTH(requested_content ->> 'requested_next_action') > 4000 THEN
            RAISE EXCEPTION 'requested_next_action must contain 1 to 4000 characters'
                USING ERRCODE = '22023';
        END IF;
        normalized_content := jsonb_set(
            normalized_content, '{requested_next_action}',
            to_jsonb(BTRIM(requested_content ->> 'requested_next_action')), TRUE
        );
    END IF;
    IF requested_content ? 'session_type' THEN
        IF jsonb_typeof(requested_content -> 'session_type') IS DISTINCT FROM 'string'
           OR requested_content ->> 'session_type' NOT IN (
                'weekly_review', 'stakeholder_health', 'relationship_review',
                'risk_triage', 'governance_followup'
           ) THEN
            RAISE EXCEPTION 'session_type is not supported' USING ERRCODE = '22023';
        END IF;
    END IF;
    IF requested_content ? 'title' THEN
        IF jsonb_typeof(requested_content -> 'title') IS DISTINCT FROM 'string'
           OR NULLIF(BTRIM(requested_content ->> 'title'), '') IS NULL
           OR CHAR_LENGTH(requested_content ->> 'title') > 255 THEN
            RAISE EXCEPTION 'title must contain 1 to 255 characters' USING ERRCODE = '22023';
        END IF;
        normalized_content := jsonb_set(
            normalized_content, '{title}', to_jsonb(BTRIM(requested_content ->> 'title')), TRUE
        );
    END IF;
    IF requested_content ? 'priority' THEN
        IF jsonb_typeof(requested_content -> 'priority') IS DISTINCT FROM 'number'
           OR requested_content ->> 'priority' !~ '^[1-5]$' THEN
            RAISE EXCEPTION 'priority must be an integer between 1 and 5'
                USING ERRCODE = '22023';
        END IF;
    END IF;
    IF requested_operation = 'create_item'
       AND jsonb_typeof(requested_content -> 'session_id') IS DISTINCT FROM 'string' THEN
        RAISE EXCEPTION 'session_id must be a UUID string' USING ERRCODE = '22023';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM unnest(ARRAY[
              'session_id', 'tension_id', 'work_item_id', 'decision_id',
              'owner_role_id', 'owner_party_id', 'facilitator_role_id', 'recorder_role_id'
          ]) AS fields(field_name)
         WHERE requested_content ? field_name
           AND requested_content -> field_name <> 'null'::jsonb
           AND (jsonb_typeof(requested_content -> field_name) IS DISTINCT FROM 'string'
                OR NULLIF(BTRIM(requested_content ->> field_name), '') IS NULL)
    ) THEN
        RAISE EXCEPTION 'tactical content identifiers must be UUID strings or null'
            USING ERRCODE = '22023';
    END IF;
    IF requested_content ? 'agenda_scope'
       AND requested_content -> 'agenda_scope' <> 'null'::jsonb
       AND (jsonb_typeof(requested_content -> 'agenda_scope') IS DISTINCT FROM 'string'
            OR CHAR_LENGTH(requested_content ->> 'agenda_scope') > 10000) THEN
        RAISE EXCEPTION 'agenda_scope must be text up to 10000 characters or null'
            USING ERRCODE = '22023';
    END IF;
    IF requested_content ? 'agenda_scope' THEN
        normalized_content := jsonb_set(
            normalized_content, '{agenda_scope}',
            COALESCE(to_jsonb(NULLIF(BTRIM(requested_content ->> 'agenda_scope'), '')), 'null'::jsonb),
            TRUE
        );
    END IF;

    BEGIN
        IF requested_content ? 'session_id' THEN
            requested_session_id := NULLIF(requested_content ->> 'session_id', '')::UUID;
        END IF;
        IF requested_content ? 'tension_id' THEN
            requested_tension_id := NULLIF(requested_content ->> 'tension_id', '')::UUID;
        END IF;
        IF requested_content ? 'work_item_id' THEN
            requested_work_item_id := NULLIF(requested_content ->> 'work_item_id', '')::UUID;
        END IF;
        IF requested_content ? 'decision_id' THEN
            requested_decision_id := NULLIF(requested_content ->> 'decision_id', '')::UUID;
        END IF;
        IF requested_content ? 'owner_role_id' THEN
            requested_owner_role_id := NULLIF(requested_content ->> 'owner_role_id', '')::UUID;
        END IF;
        IF requested_content ? 'owner_party_id' THEN
            requested_owner_party_id := NULLIF(requested_content ->> 'owner_party_id', '')::UUID;
        END IF;
        IF requested_content ? 'facilitator_role_id' THEN
            requested_facilitator_role_id := NULLIF(requested_content ->> 'facilitator_role_id', '')::UUID;
        END IF;
        IF requested_content ? 'recorder_role_id' THEN
            requested_recorder_role_id := NULLIF(requested_content ->> 'recorder_role_id', '')::UUID;
        END IF;
        IF requested_content ? 'priority' THEN
            next_priority := (requested_content ->> 'priority')::SMALLINT;
        END IF;
        IF requested_content ? 'scheduled_at'
           AND requested_content -> 'scheduled_at' <> 'null'::jsonb THEN
            IF jsonb_typeof(requested_content -> 'scheduled_at') IS DISTINCT FROM 'string'
               OR requested_content ->> 'scheduled_at' !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
                RAISE EXCEPTION 'scheduled_at requires a timezone-qualified timestamp'
                    USING ERRCODE = '22023';
            END IF;
            requested_schedule := (requested_content ->> 'scheduled_at')::TIMESTAMPTZ;
            normalized_content := jsonb_set(
                normalized_content, '{scheduled_at}', to_jsonb(requested_schedule), TRUE
            );
        ELSIF requested_content ? 'scheduled_at' THEN
            normalized_content := jsonb_set(normalized_content, '{scheduled_at}', 'null'::jsonb, TRUE);
        END IF;
        IF requested_content ? 'due_at'
           AND requested_content -> 'due_at' <> 'null'::jsonb THEN
            IF jsonb_typeof(requested_content -> 'due_at') IS DISTINCT FROM 'string'
               OR requested_content ->> 'due_at' !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
                RAISE EXCEPTION 'due_at requires a timezone-qualified timestamp'
                    USING ERRCODE = '22023';
            END IF;
            requested_due := (requested_content ->> 'due_at')::TIMESTAMPTZ;
            normalized_content := jsonb_set(
                normalized_content, '{due_at}', to_jsonb(requested_due), TRUE
            );
        ELSIF requested_content ? 'due_at' THEN
            normalized_content := jsonb_set(normalized_content, '{due_at}', 'null'::jsonb, TRUE);
        END IF;
    EXCEPTION WHEN invalid_text_representation OR datetime_field_overflow
                  OR invalid_datetime_format THEN
        RAISE EXCEPTION 'tactical content contains an invalid identifier or timestamp'
            USING ERRCODE = '22023';
    END;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 445)
    );
    SELECT event.* INTO prior_event
      FROM public.governance_tactical_content_event AS event
     WHERE event.operator_id = context_record.actor_id
       AND event.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_event.location_id IS DISTINCT FROM requested_location_id
           OR prior_event.operation IS DISTINCT FROM requested_operation
           OR prior_event.requested_content IS DISTINCT FROM normalized_content
           OR prior_event.reason IS DISTINCT FROM normalized_reason
           OR (requested_operation = 'update_session'
               AND prior_event.session_id IS DISTINCT FROM requested_target_id)
           OR (requested_operation = 'update_item'
               AND prior_event.item_id IS DISTINCT FROM requested_target_id) THEN
            RAISE EXCEPTION 'tactical content request ID was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        IF prior_event.actor_party_id IS DISTINCT FROM actor_party THEN
            RAISE EXCEPTION 'tactical content retry is not from its recorded actor binding'
                USING ERRCODE = '42501';
        END IF;
        event_id := prior_event.id;
        operation := prior_event.operation;
        session_id := prior_event.session_id;
        item_id := prior_event.item_id;
        actor_party_id := prior_event.actor_party_id;
        created_at := prior_event.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    IF requested_operation IN ('create_item', 'update_item') THEN
        IF requested_operation = 'create_item' THEN
            IF requested_content ? 'requested_next_action' IS FALSE THEN
                RAISE EXCEPTION 'requested_next_action is required' USING ERRCODE = '22023';
            END IF;
            SELECT session.id, session.circle_id, session.status,
                   circle.status AS circle_status
              INTO session_record
              FROM public.governance_tactical_session AS session
              JOIN public.governance_circle AS circle ON circle.id = session.circle_id
             WHERE session.id = requested_session_id
               AND circle.scope_type = 'location'
               AND circle.scope_id = requested_location_id
             FOR SHARE OF session, circle;
            IF FOUND THEN
                tactical_session_id := session_record.id;
                tactical_circle_id := session_record.circle_id;
                tactical_session_status := session_record.status;
                tactical_circle_status := session_record.circle_status;
            END IF;
        ELSE
            SELECT item.*, session.id AS scoped_session_id, session.circle_id,
                   session.status AS session_status, circle.status AS circle_status
              INTO item_record
              FROM public.governance_tactical_item AS item
              JOIN public.governance_tactical_session AS session ON session.id = item.session_id
              JOIN public.governance_circle AS circle ON circle.id = session.circle_id
             WHERE item.id = requested_target_id
               AND circle.scope_type = 'location'
               AND circle.scope_id = requested_location_id
             FOR UPDATE OF item;
            IF FOUND THEN
                requested_session_id := item_record.scoped_session_id;
                tactical_session_id := item_record.scoped_session_id;
                tactical_circle_id := item_record.circle_id;
                tactical_session_status := item_record.session_status;
                tactical_circle_status := item_record.circle_status;
            END IF;
        END IF;
        IF tactical_session_id IS NULL THEN
            RAISE EXCEPTION 'tactical session or item was not found in this location'
                USING ERRCODE = 'P0002';
        END IF;
        IF tactical_circle_status <> 'active' OR tactical_session_status = 'cancelled' THEN
            RAISE EXCEPTION 'tactical content requires an active circle and non-cancelled session'
                USING ERRCODE = '55000';
        END IF;

        IF requested_operation = 'create_item' THEN
            next_action := normalized_content ->> 'requested_next_action';
            next_priority := COALESCE(next_priority, 3);
            requested_due := CASE WHEN requested_content ? 'due_at' THEN requested_due ELSE NULL END;
        ELSE
            IF item_record.status <> 'open' THEN
                RAISE EXCEPTION 'only open tactical items can be edited' USING ERRCODE = '55000';
            END IF;
            next_action := item_record.requested_next_action;
            next_priority := item_record.priority;
            requested_due := item_record.due_at;
            requested_tension_id := item_record.tension_id;
            requested_work_item_id := item_record.work_item_id;
            requested_decision_id := item_record.decision_id;
            requested_owner_role_id := item_record.owner_role_id;
            requested_owner_party_id := item_record.owner_party_id;
            IF normalized_content ? 'requested_next_action' THEN
                next_action := normalized_content ->> 'requested_next_action';
            END IF;
            IF requested_content ? 'priority' THEN
                next_priority := (requested_content ->> 'priority')::SMALLINT;
            END IF;
            IF requested_content ? 'due_at' THEN
                requested_due := CASE WHEN requested_content -> 'due_at' = 'null'::jsonb
                    THEN NULL ELSE (requested_content ->> 'due_at')::TIMESTAMPTZ END;
            END IF;
            IF requested_content ? 'tension_id' THEN
                requested_tension_id := NULLIF(requested_content ->> 'tension_id', '')::UUID;
            END IF;
            IF requested_content ? 'work_item_id' THEN
                requested_work_item_id := NULLIF(requested_content ->> 'work_item_id', '')::UUID;
            END IF;
            IF requested_content ? 'decision_id' THEN
                requested_decision_id := NULLIF(requested_content ->> 'decision_id', '')::UUID;
            END IF;
            IF requested_content ? 'owner_role_id' THEN
                requested_owner_role_id := NULLIF(requested_content ->> 'owner_role_id', '')::UUID;
            END IF;
            IF requested_content ? 'owner_party_id' THEN
                requested_owner_party_id := NULLIF(requested_content ->> 'owner_party_id', '')::UUID;
            END IF;
            IF requested_content ? 'due_at' THEN
                normalized_content := jsonb_set(
                    normalized_content, '{due_at}',
                    COALESCE(to_jsonb(requested_due), 'null'::jsonb), TRUE
                );
            END IF;
        END IF;

        IF next_priority IS NULL OR next_priority NOT BETWEEN 1 AND 5 THEN
            RAISE EXCEPTION 'priority must be an integer between 1 and 5' USING ERRCODE = '22023';
        END IF;
        IF requested_owner_role_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.governance_role AS role
             WHERE role.id = requested_owner_role_id
               AND role.circle_id = tactical_circle_id
               AND role.status = 'active'
             FOR SHARE
        ) THEN
            RAISE EXCEPTION 'owner role must be active in this tactical circle'
                USING ERRCODE = 'P0002';
        END IF;
        IF requested_owner_party_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.party AS person
             WHERE person.id = requested_owner_party_id
               AND person.party_type = 'person'
               AND person.status = 'active'
             FOR SHARE
        ) THEN
            RAISE EXCEPTION 'owner party must be an active person' USING ERRCODE = 'P0002';
        END IF;
        IF requested_tension_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.governance_tension AS tension
             WHERE tension.id = requested_tension_id
               AND (
                    (tension.scope_type = 'location' AND tension.scope_id = requested_location_id)
                    OR tension.circle_id = tactical_circle_id
               )
             FOR SHARE
        ) THEN
            RAISE EXCEPTION 'tension must be scoped to this location or circle' USING ERRCODE = 'P0002';
        END IF;
        IF requested_work_item_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.work_item AS work
             WHERE work.id = requested_work_item_id
               AND work.location_id = requested_location_id
             FOR SHARE
        ) THEN
            RAISE EXCEPTION 'work item must belong to this location' USING ERRCODE = 'P0002';
        END IF;
        IF requested_decision_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.stakeholder_decision AS decision
             WHERE decision.id = requested_decision_id
               AND decision.scope_type = 'location'
               AND decision.scope_id = requested_location_id
             FOR SHARE
        ) THEN
            RAISE EXCEPTION 'decision must belong to this location' USING ERRCODE = 'P0002';
        END IF;

        IF requested_operation = 'create_item' THEN
            new_item_id := gen_random_uuid();
            INSERT INTO public.governance_tactical_item (
                id, session_id, tension_id, work_item_id, decision_id, proposer_party_id,
                owner_role_id, owner_party_id, requested_next_action, priority, due_at, status
            ) VALUES (
                new_item_id, requested_session_id, requested_tension_id,
                requested_work_item_id, requested_decision_id, actor_party,
                requested_owner_role_id, requested_owner_party_id, next_action,
                next_priority, requested_due, 'open'
            );
            session_id := requested_session_id;
            item_id := new_item_id;
            prior_content := '{}'::jsonb;
        ELSE
            prior_content := jsonb_build_object(
                'requested_next_action', item_record.requested_next_action,
                'priority', item_record.priority,
                'due_at', item_record.due_at,
                'tension_id', item_record.tension_id,
                'work_item_id', item_record.work_item_id,
                'decision_id', item_record.decision_id,
                'owner_role_id', item_record.owner_role_id,
                'owner_party_id', item_record.owner_party_id
            );
            UPDATE public.governance_tactical_item AS item
               SET tension_id = requested_tension_id,
                   work_item_id = requested_work_item_id,
                   decision_id = requested_decision_id,
                   owner_role_id = requested_owner_role_id,
                   owner_party_id = requested_owner_party_id,
                   requested_next_action = next_action,
                   priority = next_priority,
                   due_at = requested_due,
                   updated_at = clock_timestamp()
             WHERE item.id = requested_target_id;
            session_id := requested_session_id;
            item_id := requested_target_id;
        END IF;
    ELSE
        SELECT session.*, circle.status AS circle_status
          INTO session_record
          FROM public.governance_tactical_session AS session
          JOIN public.governance_circle AS circle ON circle.id = session.circle_id
         WHERE session.id = requested_target_id
           AND circle.scope_type = 'location'
           AND circle.scope_id = requested_location_id
         FOR UPDATE OF session;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'tactical session was not found in this location'
                USING ERRCODE = 'P0002';
        END IF;
        IF session_record.status <> 'planned' OR session_record.circle_status <> 'active' THEN
            RAISE EXCEPTION 'only planned sessions in active circles can be edited'
                USING ERRCODE = '55000';
        END IF;
        next_session_type := session_record.session_type;
        next_title := session_record.title;
        requested_schedule := session_record.scheduled_at;
        requested_facilitator_role_id := session_record.facilitator_role_id;
        requested_recorder_role_id := session_record.recorder_role_id;
        next_agenda_scope := session_record.agenda_scope;
        IF requested_content ? 'session_type' THEN
            next_session_type := requested_content ->> 'session_type';
        END IF;
        IF normalized_content ? 'title' THEN
            next_title := normalized_content ->> 'title';
        END IF;
        IF requested_content ? 'scheduled_at' THEN
            requested_schedule := CASE WHEN requested_content -> 'scheduled_at' = 'null'::jsonb
                THEN NULL ELSE (requested_content ->> 'scheduled_at')::TIMESTAMPTZ END;
            normalized_content := jsonb_set(
                normalized_content, '{scheduled_at}',
                COALESCE(to_jsonb(requested_schedule), 'null'::jsonb), TRUE
            );
        END IF;
        IF requested_content ? 'facilitator_role_id' THEN
            requested_facilitator_role_id := NULLIF(requested_content ->> 'facilitator_role_id', '')::UUID;
        END IF;
        IF requested_content ? 'recorder_role_id' THEN
            requested_recorder_role_id := NULLIF(requested_content ->> 'recorder_role_id', '')::UUID;
        END IF;
        IF requested_content ? 'agenda_scope' THEN
            next_agenda_scope := NULLIF(BTRIM(requested_content ->> 'agenda_scope'), '');
            normalized_content := jsonb_set(
                normalized_content, '{agenda_scope}',
                COALESCE(to_jsonb(next_agenda_scope), 'null'::jsonb), TRUE
            );
        END IF;
        FOREACH reference_id IN ARRAY ARRAY[
            requested_facilitator_role_id, requested_recorder_role_id
        ] LOOP
            IF reference_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM public.governance_role AS role
                 WHERE role.id = reference_id
                   AND role.circle_id = session_record.circle_id
                   AND role.status = 'active'
                 FOR SHARE
            ) THEN
                RAISE EXCEPTION 'session roles must be active in the selected circle'
                    USING ERRCODE = 'P0002';
            END IF;
        END LOOP;
        prior_content := jsonb_build_object(
            'session_type', session_record.session_type,
            'title', session_record.title,
            'scheduled_at', session_record.scheduled_at,
            'facilitator_role_id', session_record.facilitator_role_id,
            'recorder_role_id', session_record.recorder_role_id,
            'agenda_scope', session_record.agenda_scope
        );
        UPDATE public.governance_tactical_session AS session
           SET session_type = next_session_type,
               title = next_title,
               scheduled_at = requested_schedule,
               facilitator_role_id = requested_facilitator_role_id,
               recorder_role_id = requested_recorder_role_id,
               agenda_scope = next_agenda_scope,
               updated_at = clock_timestamp()
         WHERE session.id = requested_target_id;
        session_id := requested_target_id;
        item_id := NULL;
    END IF;

    INSERT INTO public.governance_tactical_content_event (
        operator_id, request_id, location_id, session_id, item_id,
        operation, actor_party_id, requested_content, prior_content, reason
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        session_id, item_id, requested_operation, actor_party,
        normalized_content, prior_content, normalized_reason
    ) RETURNING id, public.governance_tactical_content_event.created_at
      INTO new_event_id, event_time;
    event_id := new_event_id;
    operation := requested_operation;
    actor_party_id := actor_party;
    created_at := event_time;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.mutate_governance_tactical_content(
    UUID, TEXT, UUID, UUID, JSONB, TEXT
) OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.mutate_governance_tactical_content(
    UUID, TEXT, UUID, UUID, JSONB, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.mutate_governance_tactical_content(
            UUID, TEXT, UUID, UUID, JSONB, TEXT
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.mutate_governance_tactical_content(
            UUID, TEXT, UUID, UUID, JSONB, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_governance_action_owner;

COMMENT ON TABLE public.governance_tactical_content_event IS
    'Private append-only request, actor, reason, and before-state history for tactical item/session content mutations.';
COMMENT ON FUNCTION kokonut_security.mutate_governance_tactical_content(
    UUID, TEXT, UUID, UUID, JSONB, TEXT
) IS 'Creates tactical items and updates open items or planned sessions under exact signed location grants and immutable audit history.';

COMMIT;
