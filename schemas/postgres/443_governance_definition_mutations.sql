-- Create and edit location-scoped governance definitions only through the
-- audited Gateway path. Definitions always begin as drafts; lifecycle remains
-- governed by migration 442.

BEGIN;

CREATE TABLE IF NOT EXISTS public.governance_definition_mutation_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('circle', 'role')),
    entity_id UUID NOT NULL,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('create', 'update')),
    requested_content JSONB NOT NULL CHECK (jsonb_typeof(requested_content) = 'object'),
    before_values JSONB NOT NULL CHECK (jsonb_typeof(before_values) = 'object'),
    after_values JSONB NOT NULL CHECK (jsonb_typeof(after_values) = 'object'),
    reason TEXT NOT NULL CHECK (
        NULLIF(BTRIM(reason), '') IS NOT NULL AND CHAR_LENGTH(reason) <= 2000
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

CREATE INDEX IF NOT EXISTS idx_governance_definition_mutation_location
    ON public.governance_definition_mutation_event(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_governance_definition_mutation_event_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'governance definition mutation history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_definition_mutation_event_immutable
    ON public.governance_definition_mutation_event;
CREATE TRIGGER trg_governance_definition_mutation_event_immutable
    BEFORE UPDATE OR DELETE ON public.governance_definition_mutation_event
    FOR EACH ROW EXECUTE FUNCTION public.prevent_governance_definition_mutation_event_change();

CREATE OR REPLACE FUNCTION public.guard_governance_definition_mutation()
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
        RAISE EXCEPTION 'governance definitions require the audited Gateway mutation path';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_circle_mutation_guard ON public.governance_circle;
CREATE TRIGGER trg_governance_circle_mutation_guard
    BEFORE INSERT OR UPDATE ON public.governance_circle
    FOR EACH ROW EXECUTE FUNCTION public.guard_governance_definition_mutation();

DROP TRIGGER IF EXISTS trg_governance_role_mutation_guard ON public.governance_role;
CREATE TRIGGER trg_governance_role_mutation_guard
    BEFORE INSERT OR UPDATE ON public.governance_role
    FOR EACH ROW EXECUTE FUNCTION public.guard_governance_definition_mutation();

REVOKE ALL ON FUNCTION public.prevent_governance_definition_mutation_event_change() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.guard_governance_definition_mutation() FROM PUBLIC;

REVOKE ALL ON TABLE public.governance_definition_mutation_event FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE public.governance_definition_mutation_event
    TO kokonut_governance_action_owner;
GRANT SELECT ON TABLE public.governance_circle, public.governance_role,
    public.operator_governance_party_binding, public.operator_identity,
    public.party, public.operator_scope_grant
    TO kokonut_governance_action_owner;
GRANT INSERT (
    id, circle_key, name, purpose, description, parent_circle_id,
    scope_type, scope_id, status, created_by_party_id, metadata
) ON TABLE public.governance_circle TO kokonut_governance_action_owner;
GRANT UPDATE (circle_key, name, purpose, description, parent_circle_id)
    ON TABLE public.governance_circle TO kokonut_governance_action_owner;
GRANT INSERT (
    id, circle_id, role_key, name, purpose, status, created_by_party_id, metadata
) ON TABLE public.governance_role TO kokonut_governance_action_owner;
GRANT UPDATE (role_key, name, purpose)
    ON TABLE public.governance_role TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_governance_action_owner;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_circle,
            public.governance_role FROM kokonut_runtime;
        REVOKE ALL ON TABLE public.governance_definition_mutation_event FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_circle,
            public.governance_role FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.governance_definition_mutation_event FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.mutate_governance_definition(
    requested_location_id UUID,
    requested_entity_type TEXT,
    requested_entity_id UUID,
    requested_request_id UUID,
    requested_action TEXT,
    requested_content JSONB,
    requested_reason TEXT
)
RETURNS TABLE (
    event_id UUID,
    entity_type TEXT,
    entity_id UUID,
    action TEXT,
    actor_party_id UUID,
    created_at TIMESTAMPTZ,
    result JSONB
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party UUID;
    prior_event public.governance_definition_mutation_event%ROWTYPE;
    requested_parent_id UUID;
    requested_circle_id UUID;
    target_status TEXT;
    before_data JSONB := '{}'::jsonb;
    after_data JSONB := '{}'::jsonb;
    output_data JSONB := '{}'::jsonb;
    new_entity_id UUID;
    new_event_id UUID;
    event_time TIMESTAMPTZ;
    allowed_keys TEXT[];
    required_keys TEXT[];
    invalid_uuid BOOLEAN := FALSE;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'governance definition mutation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_entity_type IS NULL
       OR requested_entity_type NOT IN ('circle', 'role')
       OR requested_action IS NULL
       OR requested_action NOT IN ('create', 'update')
       OR requested_request_id IS NULL
       OR requested_reason IS NULL
       OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 2000
       OR requested_content IS NULL
       OR jsonb_typeof(requested_content) IS DISTINCT FROM 'object'
       OR (requested_action = 'create' AND requested_entity_id IS NOT NULL)
       OR (requested_action = 'update' AND requested_entity_id IS NULL) THEN
        RAISE EXCEPTION 'governance definition mutation arguments are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_roles', requested_action, requested_location_id
    ) THEN
        RAISE EXCEPTION 'governance definition mutation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_entity_type = 'circle' AND requested_action = 'create' THEN
        allowed_keys := ARRAY['circle_key', 'name', 'purpose', 'description', 'parent_circle_id'];
        required_keys := ARRAY['circle_key', 'name', 'purpose'];
    ELSIF requested_entity_type = 'circle' THEN
        allowed_keys := ARRAY['circle_key', 'name', 'purpose', 'description', 'parent_circle_id'];
        required_keys := ARRAY[]::text[];
    ELSIF requested_action = 'create' THEN
        allowed_keys := ARRAY['circle_id', 'role_key', 'name', 'purpose'];
        required_keys := ARRAY['circle_id', 'role_key', 'name', 'purpose'];
    ELSE
        allowed_keys := ARRAY['role_key', 'name', 'purpose'];
        required_keys := ARRAY[]::text[];
    END IF;

    IF EXISTS (
           SELECT 1 FROM jsonb_object_keys(requested_content) AS content_key
            WHERE NOT (content_key = ANY(allowed_keys))
       )
       OR EXISTS (
           SELECT 1 FROM unnest(required_keys) AS required_key
            WHERE NOT (requested_content ? required_key)
               OR requested_content -> required_key = 'null'::jsonb
       )
       OR (requested_action = 'update' AND requested_content = '{}'::jsonb) THEN
        RAISE EXCEPTION 'governance definition content has missing or unsupported fields'
            USING ERRCODE = '22023';
    END IF;

    IF requested_entity_type = 'circle' THEN
        IF jsonb_typeof(requested_content -> 'circle_key') IS NOT NULL
           AND (jsonb_typeof(requested_content -> 'circle_key') IS DISTINCT FROM 'string'
             OR NULLIF(BTRIM(requested_content ->> 'circle_key'), '') IS NULL
             OR CHAR_LENGTH(requested_content ->> 'circle_key') > 120) THEN
            RAISE EXCEPTION 'circle_key must contain 1 to 120 characters' USING ERRCODE = '22023';
        END IF;
        IF jsonb_typeof(requested_content -> 'name') IS NOT NULL
           AND (jsonb_typeof(requested_content -> 'name') IS DISTINCT FROM 'string'
             OR NULLIF(BTRIM(requested_content ->> 'name'), '') IS NULL
             OR CHAR_LENGTH(requested_content ->> 'name') > 255) THEN
            RAISE EXCEPTION 'name must contain 1 to 255 characters' USING ERRCODE = '22023';
        END IF;
        IF jsonb_typeof(requested_content -> 'purpose') IS NOT NULL
           AND (jsonb_typeof(requested_content -> 'purpose') IS DISTINCT FROM 'string'
             OR NULLIF(BTRIM(requested_content ->> 'purpose'), '') IS NULL
             OR CHAR_LENGTH(requested_content ->> 'purpose') > 10000) THEN
            RAISE EXCEPTION 'purpose must contain 1 to 10000 characters' USING ERRCODE = '22023';
        END IF;
        IF requested_content ? 'description'
           AND (jsonb_typeof(requested_content -> 'description') IS DISTINCT FROM 'string'
             OR CHAR_LENGTH(requested_content ->> 'description') > 10000) THEN
            RAISE EXCEPTION 'description must contain at most 10000 characters' USING ERRCODE = '22023';
        END IF;
        IF requested_content ? 'parent_circle_id' THEN
            IF requested_content -> 'parent_circle_id' <> 'null'::jsonb THEN
                BEGIN
                    requested_parent_id := (requested_content ->> 'parent_circle_id')::uuid;
                EXCEPTION WHEN invalid_text_representation THEN
                    invalid_uuid := TRUE;
                END;
                IF invalid_uuid THEN
                    RAISE EXCEPTION 'parent_circle_id must be a UUID or null' USING ERRCODE = '22023';
                END IF;
            ELSE
                requested_parent_id := NULL;
            END IF;
        END IF;
    ELSE
        IF requested_action = 'create' THEN
            BEGIN
                requested_circle_id := (requested_content ->> 'circle_id')::uuid;
            EXCEPTION WHEN invalid_text_representation THEN
                invalid_uuid := TRUE;
            END;
            IF invalid_uuid OR requested_circle_id IS NULL THEN
                RAISE EXCEPTION 'circle_id must be a UUID' USING ERRCODE = '22023';
            END IF;
        END IF;
        IF jsonb_typeof(requested_content -> 'role_key') IS NOT NULL
           AND (jsonb_typeof(requested_content -> 'role_key') IS DISTINCT FROM 'string'
             OR NULLIF(BTRIM(requested_content ->> 'role_key'), '') IS NULL
             OR CHAR_LENGTH(requested_content ->> 'role_key') > 120) THEN
            RAISE EXCEPTION 'role_key must contain 1 to 120 characters' USING ERRCODE = '22023';
        END IF;
        IF jsonb_typeof(requested_content -> 'name') IS NOT NULL
           AND (jsonb_typeof(requested_content -> 'name') IS DISTINCT FROM 'string'
             OR NULLIF(BTRIM(requested_content ->> 'name'), '') IS NULL
             OR CHAR_LENGTH(requested_content ->> 'name') > 255) THEN
            RAISE EXCEPTION 'name must contain 1 to 255 characters' USING ERRCODE = '22023';
        END IF;
        IF jsonb_typeof(requested_content -> 'purpose') IS NOT NULL
           AND (jsonb_typeof(requested_content -> 'purpose') IS DISTINCT FROM 'string'
             OR NULLIF(BTRIM(requested_content ->> 'purpose'), '') IS NULL
             OR CHAR_LENGTH(requested_content ->> 'purpose') > 10000) THEN
            RAISE EXCEPTION 'purpose must contain 1 to 10000 characters' USING ERRCODE = '22023';
        END IF;
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
        RAISE EXCEPTION 'governance definition mutation requires an active person binding'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 443)
    );
    SELECT event.* INTO prior_event
      FROM public.governance_definition_mutation_event AS event
     WHERE event.operator_id = context_record.actor_id
       AND event.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_event.location_id IS DISTINCT FROM requested_location_id
           OR prior_event.entity_type IS DISTINCT FROM requested_entity_type
           OR prior_event.action IS DISTINCT FROM requested_action
           OR prior_event.requested_content IS DISTINCT FROM requested_content
           OR prior_event.reason IS DISTINCT FROM BTRIM(requested_reason)
           OR (requested_action = 'update' AND prior_event.entity_id IS DISTINCT FROM requested_entity_id) THEN
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
        actor_party_id := prior_event.actor_party_id;
        created_at := prior_event.created_at;
        result := prior_event.after_values || jsonb_build_object('id', prior_event.entity_id);
        RETURN NEXT;
        RETURN;
    END IF;

    IF requested_entity_type = 'circle' THEN
        IF requested_action = 'create' THEN
            IF requested_content ? 'parent_circle_id' AND requested_parent_id IS NOT NULL
               AND NOT EXISTS (
                    SELECT 1 FROM public.governance_circle AS parent
                     WHERE parent.id = requested_parent_id
                       AND parent.scope_type = 'location'
                       AND parent.scope_id = requested_location_id
                       AND parent.status IN ('draft', 'active')
               ) THEN
                RAISE EXCEPTION 'parent circle must be a draft or active circle in this location'
                    USING ERRCODE = '22023';
            END IF;
            new_entity_id := gen_random_uuid();
            INSERT INTO public.governance_circle (
                id, circle_key, name, purpose, description, parent_circle_id,
                scope_type, scope_id, status, created_by_party_id, metadata
            ) VALUES (
                new_entity_id, BTRIM(requested_content ->> 'circle_key'),
                BTRIM(requested_content ->> 'name'), BTRIM(requested_content ->> 'purpose'),
                COALESCE(requested_content ->> 'description', ''), requested_parent_id,
                'location', requested_location_id, 'draft', actor_party, '{}'::jsonb
            );
            after_data := jsonb_build_object(
                'id', new_entity_id, 'circle_key', BTRIM(requested_content ->> 'circle_key'),
                'name', BTRIM(requested_content ->> 'name'),
                'purpose', BTRIM(requested_content ->> 'purpose'),
                'description', COALESCE(requested_content ->> 'description', ''),
                'parent_circle_id', requested_parent_id, 'status', 'draft'
            );
        ELSE
            SELECT jsonb_build_object(
                       'circle_key', circle.circle_key, 'name', circle.name,
                       'purpose', circle.purpose, 'description', circle.description,
                       'parent_circle_id', circle.parent_circle_id, 'status', circle.status
                   )
              INTO before_data
              FROM public.governance_circle AS circle
             WHERE circle.id = requested_entity_id
               AND circle.scope_type = 'location'
               AND circle.scope_id = requested_location_id
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'governance circle was not found in this location' USING ERRCODE = 'P0002';
            END IF;
            IF before_data ->> 'status' <> 'draft' THEN
                RAISE EXCEPTION 'only draft governance definitions can be edited' USING ERRCODE = '55000';
            END IF;
            IF requested_content ? 'parent_circle_id' AND requested_parent_id IS NOT NULL THEN
                IF requested_parent_id = requested_entity_id
                   OR NOT EXISTS (
                        SELECT 1 FROM public.governance_circle AS parent
                         WHERE parent.id = requested_parent_id
                           AND parent.scope_type = 'location'
                           AND parent.scope_id = requested_location_id
                           AND parent.status IN ('draft', 'active')
                   ) THEN
                    RAISE EXCEPTION 'parent circle must be a different draft or active circle in this location'
                        USING ERRCODE = '22023';
                END IF;
                IF EXISTS (
                    WITH RECURSIVE descendants(id) AS (
                        SELECT child.id FROM public.governance_circle AS child
                         WHERE child.parent_circle_id = requested_entity_id
                        UNION
                        SELECT child.id FROM public.governance_circle AS child
                         JOIN descendants ON child.parent_circle_id = descendants.id
                    )
                    SELECT 1 FROM descendants WHERE id = requested_parent_id
                ) THEN
                    RAISE EXCEPTION 'circle hierarchy cannot contain a cycle' USING ERRCODE = '22023';
                END IF;
            END IF;
            UPDATE public.governance_circle AS circle
               SET circle_key = CASE WHEN requested_content ? 'circle_key' THEN BTRIM(requested_content ->> 'circle_key') ELSE circle.circle_key END,
                   name = CASE WHEN requested_content ? 'name' THEN BTRIM(requested_content ->> 'name') ELSE circle.name END,
                   purpose = CASE WHEN requested_content ? 'purpose' THEN BTRIM(requested_content ->> 'purpose') ELSE circle.purpose END,
                   description = CASE WHEN requested_content ? 'description' THEN requested_content ->> 'description' ELSE circle.description END,
                   parent_circle_id = CASE WHEN requested_content ? 'parent_circle_id' THEN requested_parent_id ELSE circle.parent_circle_id END
             WHERE circle.id = requested_entity_id
            RETURNING jsonb_build_object(
                'circle_key', circle.circle_key, 'name', circle.name, 'purpose', circle.purpose,
                'description', circle.description, 'parent_circle_id', circle.parent_circle_id,
                'status', circle.status
            ) INTO after_data;
            new_entity_id := requested_entity_id;
        END IF;
    ELSE
        IF requested_action = 'create' THEN
            IF NOT EXISTS (
                SELECT 1 FROM public.governance_circle AS circle
                 WHERE circle.id = requested_circle_id
                   AND circle.scope_type = 'location'
                   AND circle.scope_id = requested_location_id
                   AND circle.status IN ('draft', 'active')
            ) THEN
                RAISE EXCEPTION 'role circle must be a draft or active circle in this location'
                    USING ERRCODE = 'P0002';
            END IF;
            new_entity_id := gen_random_uuid();
            INSERT INTO public.governance_role (
                id, circle_id, role_key, name, purpose, status, created_by_party_id, metadata
            ) VALUES (
                new_entity_id, requested_circle_id, BTRIM(requested_content ->> 'role_key'),
                BTRIM(requested_content ->> 'name'), BTRIM(requested_content ->> 'purpose'),
                'draft', actor_party, '{}'::jsonb
            );
            after_data := jsonb_build_object(
                'id', new_entity_id, 'circle_id', requested_circle_id,
                'role_key', BTRIM(requested_content ->> 'role_key'),
                'name', BTRIM(requested_content ->> 'name'),
                'purpose', BTRIM(requested_content ->> 'purpose'), 'status', 'draft'
            );
        ELSE
            SELECT jsonb_build_object(
                       'circle_id', role.circle_id, 'role_key', role.role_key,
                       'name', role.name, 'purpose', role.purpose, 'status', role.status
                   )
              INTO before_data
              FROM public.governance_role AS role
              JOIN public.governance_circle AS circle ON circle.id = role.circle_id
             WHERE role.id = requested_entity_id
               AND circle.scope_type = 'location'
               AND circle.scope_id = requested_location_id
             FOR UPDATE OF role;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'governance role was not found in this location' USING ERRCODE = 'P0002';
            END IF;
            IF before_data ->> 'status' <> 'draft' THEN
                RAISE EXCEPTION 'only draft governance definitions can be edited' USING ERRCODE = '55000';
            END IF;
            UPDATE public.governance_role AS role
               SET role_key = CASE WHEN requested_content ? 'role_key' THEN BTRIM(requested_content ->> 'role_key') ELSE role.role_key END,
                   name = CASE WHEN requested_content ? 'name' THEN BTRIM(requested_content ->> 'name') ELSE role.name END,
                   purpose = CASE WHEN requested_content ? 'purpose' THEN BTRIM(requested_content ->> 'purpose') ELSE role.purpose END
             WHERE role.id = requested_entity_id
            RETURNING jsonb_build_object(
                'circle_id', role.circle_id, 'role_key', role.role_key,
                'name', role.name, 'purpose', role.purpose, 'status', role.status
            ) INTO after_data;
            new_entity_id := requested_entity_id;
        END IF;
    END IF;

    IF requested_action = 'update' AND before_data = after_data THEN
        RAISE EXCEPTION 'governance definition update has no changes' USING ERRCODE = '55000';
    END IF;

    output_data := after_data || jsonb_build_object('id', new_entity_id);
    INSERT INTO public.governance_definition_mutation_event (
        operator_id, request_id, location_id, entity_type, entity_id, actor_party_id,
        action, requested_content, before_values, after_values, reason
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_entity_type, new_entity_id, actor_party, requested_action,
        requested_content, before_data, after_data, BTRIM(requested_reason)
    ) RETURNING id, public.governance_definition_mutation_event.created_at
      INTO new_event_id, event_time;

    event_id := new_event_id;
    entity_type := requested_entity_type;
    entity_id := new_entity_id;
    action := requested_action;
    actor_party_id := actor_party;
    created_at := event_time;
    result := output_data;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.mutate_governance_definition(UUID, TEXT, UUID, UUID, TEXT, JSONB, TEXT)
    OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.mutate_governance_definition(UUID, TEXT, UUID, UUID, TEXT, JSONB, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.mutate_governance_definition(UUID, TEXT, UUID, UUID, TEXT, JSONB, TEXT)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.mutate_governance_definition(UUID, TEXT, UUID, UUID, TEXT, JSONB, TEXT)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_governance_action_owner;

COMMENT ON TABLE public.governance_definition_mutation_event IS
    'Private append-only request, actor, reason, and field history for location-scoped governance circle and role creation and draft edits.';
COMMENT ON FUNCTION kokonut_security.mutate_governance_definition(UUID, TEXT, UUID, UUID, TEXT, JSONB, TEXT) IS
    'Creates location-scoped governance circles and roles as drafts or edits draft-only fields with exact grants and immutable actor history.';

COMMIT;
