-- Add audited, idempotent location-scoped governance-tension lifecycle actions.
-- Existing CLI/service paths remain available; this is the bounded Gateway path.

BEGIN;

CREATE TABLE IF NOT EXISTS public.governance_tension_action_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    tension_id UUID NOT NULL REFERENCES public.governance_tension(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'triage', 'start', 'link', 'link_work_item', 'resolve', 'defer'
    )),
    requested_content JSONB NOT NULL CHECK (jsonb_typeof(requested_content) = 'object'),
    reason TEXT NOT NULL CHECK (
        NULLIF(BTRIM(reason), '') IS NOT NULL AND CHAR_LENGTH(reason) <= 2000
    ),
    from_status TEXT NOT NULL,
    result_status TEXT NOT NULL,
    result_updated_at TIMESTAMPTZ NOT NULL,
    link_id UUID REFERENCES public.governance_tension_link(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

CREATE INDEX IF NOT EXISTS idx_governance_tension_action_request_location
    ON public.governance_tension_action_request(location_id, created_at DESC, id DESC);

-- Give the pre-existing natural-key constraint a stable short name so the
-- SECURITY DEFINER routine can use ON CONFLICT without PL/pgSQL output-column
-- ambiguity. Preserve its existing unique index by renaming the constraint.
DO $$
DECLARE
    existing_name TEXT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.governance_tension_link'::regclass
           AND conname = 'governance_tension_link_action_identity_key'
    ) THEN
        SELECT constraint_row.conname INTO existing_name
          FROM pg_catalog.pg_constraint AS constraint_row
         WHERE constraint_row.conrelid = 'public.governance_tension_link'::regclass
           AND constraint_row.contype = 'u'
           AND pg_catalog.pg_get_constraintdef(constraint_row.oid)
               = 'UNIQUE (tension_id, link_type, entity_type, entity_id)'
         LIMIT 1;
        IF existing_name IS NULL THEN
            RAISE EXCEPTION 'governance tension natural-key constraint is missing';
        END IF;
        EXECUTE pg_catalog.format(
            'ALTER TABLE public.governance_tension_link RENAME CONSTRAINT %I TO %I',
            existing_name, 'governance_tension_link_action_identity_key'
        );
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.prevent_governance_tension_action_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'governance tension action receipts are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_tension_action_request_immutable
    ON public.governance_tension_action_request;
CREATE TRIGGER trg_governance_tension_action_request_immutable
    BEFORE UPDATE OR DELETE ON public.governance_tension_action_request
    FOR EACH ROW EXECUTE FUNCTION public.prevent_governance_tension_action_request_mutation();

REVOKE ALL ON FUNCTION public.prevent_governance_tension_action_request_mutation() FROM PUBLIC;
REVOKE ALL ON TABLE public.governance_tension_action_request FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE public.governance_tension_action_request
    TO kokonut_governance_action_owner;

-- The no-login definer receives only the reads needed to validate references,
-- and the narrow columns needed to perform the governed state changes.
GRANT SELECT ON TABLE
    public.location,
    public.governance_tension,
    public.governance_tension_link,
    public.governance_tension_action_request,
    public.governance_circle,
    public.governance_role,
    public.work_item,
    public.stakeholder_interest,
    public.stakeholder_engagement_plan,
    public.stakeholder_commitment,
    public.stakeholder_decision,
    public.stakeholder_decision_evidence,
    public.stakeholder_decision_outcome,
    public.stakeholder_engagement_outcome,
    public.stakeholder_grievance_case,
    public.grievance_evidence,
    public.party_relationship,
    public.governance_proposal,
    public.operator_governance_party_binding,
    public.operator_identity,
    public.operator_scope_grant,
    public.party
TO kokonut_governance_action_owner;
GRANT UPDATE (
    owner_role_id, owner_party_id, review_due_at, status, work_item_id,
    resolution_summary, deferred_until, updated_at
) ON TABLE public.governance_tension TO kokonut_governance_action_owner;
GRANT INSERT ON TABLE public.governance_tension_link TO kokonut_governance_action_owner;
GRANT UPDATE (summary, created_by_party_id)
    ON TABLE public.governance_tension_link TO kokonut_governance_action_owner;
GRANT INSERT ON TABLE public.governance_tension_event TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_governance_action_owner;

CREATE OR REPLACE FUNCTION kokonut_security.mutate_governance_tension_action(
    requested_location_id UUID,
    requested_tension_id UUID,
    requested_action TEXT,
    requested_request_id UUID,
    requested_content JSONB,
    requested_reason TEXT
)
RETURNS TABLE (
    tension_id UUID,
    action TEXT,
    status TEXT,
    updated_at TIMESTAMPTZ,
    request_id UUID,
    link_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party UUID;
    tension_record public.governance_tension%ROWTYPE;
    prior_request public.governance_tension_action_request%ROWTYPE;
    normalized_content JSONB;
    allowed_keys TEXT[];
    required_keys TEXT[];
    required_link_type TEXT;
    requested_owner_role UUID;
    requested_owner_party UUID;
    requested_entity UUID;
    requested_work_item UUID;
    requested_due TIMESTAMPTZ;
    requested_link_type TEXT;
    requested_entity_type TEXT;
    next_status TEXT;
    event_action TEXT;
    event_link_id UUID;
    action_time TIMESTAMPTZ;
    normalized_reason TEXT;
BEGIN
    IF requested_location_id IS NULL OR requested_tension_id IS NULL
       OR requested_request_id IS NULL OR requested_action IS NULL
       OR requested_action NOT IN (
            'triage', 'start', 'link', 'link_work_item', 'resolve', 'defer'
       )
       OR requested_content IS NULL
       OR jsonb_typeof(requested_content) IS DISTINCT FROM 'object'
       OR requested_reason IS NULL
       OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 2000 THEN
        RAISE EXCEPTION 'governance tension action arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'governance tension action requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_tension', requested_action, requested_location_id
    ) THEN
        RAISE EXCEPTION 'governance tension action requires an exact active location grant'
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
        RAISE EXCEPTION 'governance tension action requires an active person binding'
            USING ERRCODE = '42501';
    END IF;

    IF requested_action = 'triage' THEN
        allowed_keys := ARRAY['owner_role_id', 'owner_party_id', 'review_due_at', 'note'];
        required_keys := ARRAY[]::TEXT[];
    ELSIF requested_action = 'start' THEN
        allowed_keys := ARRAY[]::TEXT[];
        required_keys := ARRAY[]::TEXT[];
    ELSIF requested_action = 'link' THEN
        allowed_keys := ARRAY['link_type', 'entity_type', 'entity_id', 'summary'];
        required_keys := ARRAY['link_type', 'entity_type', 'entity_id'];
    ELSIF requested_action = 'link_work_item' THEN
        allowed_keys := ARRAY['work_item_id'];
        required_keys := ARRAY['work_item_id'];
    ELSIF requested_action = 'resolve' THEN
        allowed_keys := ARRAY['resolution_summary'];
        required_keys := ARRAY['resolution_summary'];
    ELSE
        allowed_keys := ARRAY['deferred_until', 'note'];
        required_keys := ARRAY['deferred_until'];
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_object_keys(requested_content) AS key_name
         WHERE NOT (key_name = ANY(allowed_keys))
    ) OR NOT (requested_content ?& required_keys)
       OR (requested_action = 'start' AND requested_content <> '{}'::JSONB) THEN
        RAISE EXCEPTION 'governance tension action has missing or unsupported fields'
            USING ERRCODE = '22023';
    END IF;

    normalized_content := requested_content;
    normalized_reason := BTRIM(requested_reason);
    BEGIN
        IF requested_action = 'triage' THEN
            IF requested_content ? 'owner_role_id' THEN
                IF requested_content -> 'owner_role_id' <> 'null'::JSONB
                   AND jsonb_typeof(requested_content -> 'owner_role_id') IS DISTINCT FROM 'string' THEN
                    RAISE EXCEPTION 'owner_role_id must be a UUID string or null' USING ERRCODE = '22023';
                END IF;
                IF requested_content -> 'owner_role_id' <> 'null'::JSONB THEN
                    requested_owner_role := (requested_content ->> 'owner_role_id')::UUID;
                    normalized_content := jsonb_set(normalized_content, '{owner_role_id}',
                        to_jsonb(requested_owner_role::TEXT), TRUE);
                END IF;
            END IF;
            IF requested_content ? 'owner_party_id' THEN
                IF requested_content -> 'owner_party_id' <> 'null'::JSONB
                   AND jsonb_typeof(requested_content -> 'owner_party_id') IS DISTINCT FROM 'string' THEN
                    RAISE EXCEPTION 'owner_party_id must be a UUID string or null' USING ERRCODE = '22023';
                END IF;
                IF requested_content -> 'owner_party_id' <> 'null'::JSONB THEN
                    requested_owner_party := (requested_content ->> 'owner_party_id')::UUID;
                    normalized_content := jsonb_set(normalized_content, '{owner_party_id}',
                        to_jsonb(requested_owner_party::TEXT), TRUE);
                END IF;
            END IF;
            IF requested_owner_role IS NULL AND requested_owner_party IS NULL THEN
                RAISE EXCEPTION 'triage requires an owner role or party' USING ERRCODE = '22023';
            END IF;
            IF requested_content ? 'review_due_at'
               AND requested_content -> 'review_due_at' <> 'null'::JSONB THEN
                IF jsonb_typeof(requested_content -> 'review_due_at') IS DISTINCT FROM 'string'
                   OR requested_content ->> 'review_due_at' !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
                    RAISE EXCEPTION 'review_due_at requires a timezone-qualified timestamp'
                        USING ERRCODE = '22023';
                END IF;
                requested_due := (requested_content ->> 'review_due_at')::TIMESTAMPTZ;
                normalized_content := jsonb_set(normalized_content, '{review_due_at}',
                    to_jsonb(requested_due), TRUE);
            END IF;
            IF requested_content ? 'note'
               AND requested_content -> 'note' <> 'null'::JSONB
               AND (jsonb_typeof(requested_content -> 'note') IS DISTINCT FROM 'string'
                    OR CHAR_LENGTH(requested_content ->> 'note') > 2000) THEN
                RAISE EXCEPTION 'note must be text up to 2000 characters or null'
                    USING ERRCODE = '22023';
            END IF;
        ELSIF requested_action = 'link' THEN
            requested_link_type := requested_content ->> 'link_type';
            requested_entity_type := requested_content ->> 'entity_type';
            IF jsonb_typeof(requested_content -> 'link_type') IS DISTINCT FROM 'string'
               OR requested_link_type NOT IN (
                    'interest', 'commitment', 'work_item', 'decision', 'grievance',
                    'evidence', 'relationship', 'proposal', 'outcome'
               )
               OR jsonb_typeof(requested_content -> 'entity_type') IS DISTINCT FROM 'string'
               OR requested_entity_type !~ '^[a-z][a-z0-9_]{0,79}$'
               OR jsonb_typeof(requested_content -> 'entity_id') IS DISTINCT FROM 'string' THEN
                RAISE EXCEPTION 'governance tension link reference is invalid' USING ERRCODE = '22023';
            END IF;
            requested_entity := (requested_content ->> 'entity_id')::UUID;
            normalized_content := jsonb_set(normalized_content, '{entity_id}',
                to_jsonb(requested_entity::TEXT), TRUE);
            IF requested_content ? 'summary'
               AND requested_content -> 'summary' <> 'null'::JSONB
               AND (jsonb_typeof(requested_content -> 'summary') IS DISTINCT FROM 'string'
                    OR CHAR_LENGTH(requested_content ->> 'summary') > 4000) THEN
                RAISE EXCEPTION 'summary must be text up to 4000 characters or null'
                    USING ERRCODE = '22023';
            END IF;
        ELSIF requested_action = 'link_work_item' THEN
            IF jsonb_typeof(requested_content -> 'work_item_id') IS DISTINCT FROM 'string' THEN
                RAISE EXCEPTION 'work_item_id must be a UUID string' USING ERRCODE = '22023';
            END IF;
            requested_work_item := (requested_content ->> 'work_item_id')::UUID;
            normalized_content := jsonb_set(normalized_content, '{work_item_id}',
                to_jsonb(requested_work_item::TEXT), TRUE);
        ELSIF requested_action = 'resolve' THEN
            IF jsonb_typeof(requested_content -> 'resolution_summary') IS DISTINCT FROM 'string'
               OR NULLIF(BTRIM(requested_content ->> 'resolution_summary'), '') IS NULL
               OR CHAR_LENGTH(requested_content ->> 'resolution_summary') > 4000 THEN
                RAISE EXCEPTION 'resolution_summary must contain 1 to 4000 characters'
                    USING ERRCODE = '22023';
            END IF;
            normalized_content := jsonb_set(normalized_content, '{resolution_summary}',
                to_jsonb(BTRIM(requested_content ->> 'resolution_summary')), TRUE);
        ELSIF requested_action = 'defer' THEN
            IF jsonb_typeof(requested_content -> 'deferred_until') IS DISTINCT FROM 'string'
               OR requested_content ->> 'deferred_until' !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
                RAISE EXCEPTION 'deferred_until requires a timezone-qualified timestamp'
                    USING ERRCODE = '22023';
            END IF;
            requested_due := (requested_content ->> 'deferred_until')::TIMESTAMPTZ;
            normalized_content := jsonb_set(normalized_content, '{deferred_until}',
                to_jsonb(requested_due), TRUE);
            IF requested_content ? 'note'
               AND requested_content -> 'note' <> 'null'::JSONB
               AND (jsonb_typeof(requested_content -> 'note') IS DISTINCT FROM 'string'
                    OR CHAR_LENGTH(requested_content ->> 'note') > 2000) THEN
                RAISE EXCEPTION 'note must be text up to 2000 characters or null'
                    USING ERRCODE = '22023';
            END IF;
        END IF;
    EXCEPTION WHEN invalid_text_representation OR datetime_field_overflow
                  OR invalid_datetime_format THEN
        RAISE EXCEPTION 'governance tension action contains an invalid UUID or timestamp'
            USING ERRCODE = '22023';
    END;

    IF requested_action = 'link' THEN
        required_link_type := CASE requested_entity_type
            WHEN 'stakeholder_interest' THEN 'interest'
            WHEN 'stakeholder_commitment' THEN 'commitment'
            WHEN 'work_item' THEN 'work_item'
            WHEN 'stakeholder_decision' THEN 'decision'
            WHEN 'stakeholder_grievance_case' THEN 'grievance'
            WHEN 'stakeholder_decision_evidence' THEN 'evidence'
            WHEN 'grievance_evidence' THEN 'evidence'
            WHEN 'party_relationship' THEN 'relationship'
            WHEN 'governance_proposal' THEN 'proposal'
            WHEN 'stakeholder_decision_outcome' THEN 'outcome'
            WHEN 'stakeholder_engagement_outcome' THEN 'outcome'
            ELSE NULL
        END;
        IF requested_link_type IS DISTINCT FROM required_link_type THEN
            RAISE EXCEPTION 'link type and entity type are not a supported pair'
                USING ERRCODE = '22023';
        END IF;
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 700)
    );
    SELECT receipt.* INTO prior_request
      FROM public.governance_tension_action_request AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_request.actor_party_id IS DISTINCT FROM actor_party THEN
            RAISE EXCEPTION 'governance tension retry has a different person binding'
                USING ERRCODE = '42501';
        END IF;
        IF prior_request.location_id IS DISTINCT FROM requested_location_id
           OR prior_request.tension_id IS DISTINCT FROM requested_tension_id
           OR prior_request.action IS DISTINCT FROM requested_action
           OR prior_request.requested_content IS DISTINCT FROM normalized_content
           OR prior_request.reason IS DISTINCT FROM normalized_reason THEN
            RAISE EXCEPTION 'governance tension request ID was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        tension_id := prior_request.tension_id;
        action := prior_request.action;
        status := prior_request.result_status;
        updated_at := prior_request.result_updated_at;
        request_id := prior_request.request_id;
        link_id := prior_request.link_id;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT tension.* INTO tension_record
      FROM public.governance_tension AS tension
     WHERE tension.id = requested_tension_id
     FOR UPDATE OF tension;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'governance tension was not found for this location'
            USING ERRCODE = 'P0002';
    END IF;
    IF tension_record.scope_type IS DISTINCT FROM 'location'
       OR tension_record.scope_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'governance tension was not found for this location'
            USING ERRCODE = 'P0002';
    END IF;

    IF requested_action = 'triage' THEN
        IF tension_record.status NOT IN ('submitted', 'triaged') THEN
            RAISE EXCEPTION 'governance tension cannot be triaged from its current state'
                USING ERRCODE = '55000';
        END IF;
        IF requested_owner_role IS NOT NULL AND NOT EXISTS (
            SELECT 1
              FROM public.governance_role AS role
              JOIN public.governance_circle AS circle ON circle.id = role.circle_id
             WHERE role.id = requested_owner_role
               AND role.status = 'active'
               AND circle.status = 'active'
               AND circle.scope_type = 'location'
               AND circle.scope_id = requested_location_id
        ) THEN
            RAISE EXCEPTION 'owner role is not active in this location'
                USING ERRCODE = '22023';
        END IF;
        IF requested_owner_party IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.party AS person
             WHERE person.id = requested_owner_party
               AND person.party_type = 'person' AND person.status = 'active'
        ) THEN
            RAISE EXCEPTION 'owner party is not an active person'
                USING ERRCODE = '22023';
        END IF;
        UPDATE public.governance_tension AS tension
           SET owner_role_id = COALESCE(requested_owner_role, tension.owner_role_id),
               owner_party_id = COALESCE(requested_owner_party, tension.owner_party_id),
               review_due_at = CASE WHEN normalized_content ? 'review_due_at'
                   THEN requested_due ELSE tension.review_due_at END,
               status = 'triaged', updated_at = clock_timestamp()
         WHERE tension.id = requested_tension_id
         RETURNING tension.updated_at INTO action_time;
        next_status := 'triaged';
        event_action := 'triaged';
    ELSIF requested_action = 'start' THEN
        IF tension_record.status NOT IN ('triaged', 'deferred') THEN
            RAISE EXCEPTION 'governance tension cannot be started from its current state'
                USING ERRCODE = '55000';
        END IF;
        UPDATE public.governance_tension AS tension
           SET status = 'in_progress', updated_at = clock_timestamp()
         WHERE tension.id = requested_tension_id
         RETURNING tension.updated_at INTO action_time;
        next_status := 'in_progress';
        event_action := 'started';
    ELSIF requested_action = 'link' THEN
        IF tension_record.status NOT IN ('submitted', 'triaged', 'in_progress', 'deferred') THEN
            RAISE EXCEPTION 'governance tension cannot be linked from its current state'
                USING ERRCODE = '55000';
        END IF;
        IF NOT (
            (requested_entity_type = 'work_item' AND EXISTS (
                SELECT 1 FROM public.work_item AS item
                 WHERE item.id = requested_entity AND item.location_id = requested_location_id
            )) OR (requested_entity_type = 'stakeholder_interest' AND EXISTS (
                SELECT 1 FROM public.stakeholder_interest AS interest
                 WHERE interest.id = requested_entity
                   AND interest.scope_type = 'location' AND interest.scope_id = requested_location_id
            )) OR (requested_entity_type = 'stakeholder_commitment' AND EXISTS (
                SELECT 1 FROM public.stakeholder_commitment AS commitment
                JOIN public.stakeholder_engagement_plan AS plan ON plan.id = commitment.plan_id
                 WHERE commitment.id = requested_entity
                   AND plan.scope_type = 'location' AND plan.scope_id = requested_location_id
            )) OR (requested_entity_type = 'stakeholder_decision' AND EXISTS (
                SELECT 1 FROM public.stakeholder_decision AS decision
                 WHERE decision.id = requested_entity
                   AND decision.scope_type = 'location' AND decision.scope_id = requested_location_id
            )) OR (requested_entity_type = 'stakeholder_grievance_case' AND EXISTS (
                SELECT 1 FROM public.stakeholder_grievance_case AS grievance
                 WHERE grievance.id = requested_entity AND grievance.location_id = requested_location_id
            )) OR (requested_entity_type = 'stakeholder_decision_evidence' AND EXISTS (
                SELECT 1 FROM public.stakeholder_decision_evidence AS evidence
                JOIN public.stakeholder_decision AS decision ON decision.id = evidence.decision_id
                 WHERE evidence.id = requested_entity
                   AND decision.scope_type = 'location' AND decision.scope_id = requested_location_id
            )) OR (requested_entity_type = 'grievance_evidence' AND EXISTS (
                SELECT 1 FROM public.grievance_evidence AS evidence
                JOIN public.stakeholder_grievance_case AS grievance ON grievance.id = evidence.case_id
                 WHERE evidence.id = requested_entity AND grievance.location_id = requested_location_id
            )) OR (requested_entity_type = 'party_relationship' AND EXISTS (
                SELECT 1 FROM public.party_relationship AS relationship
                 WHERE relationship.id = requested_entity
                   AND relationship.scope_type = 'location' AND relationship.scope_id = requested_location_id
            )) OR (requested_entity_type = 'governance_proposal' AND EXISTS (
                SELECT 1 FROM public.governance_proposal AS proposal
                 WHERE proposal.id = requested_entity
                   AND proposal.affected_scope_type = 'location'
                   AND proposal.affected_scope_id = requested_location_id
            )) OR (requested_entity_type = 'stakeholder_decision_outcome' AND EXISTS (
                SELECT 1 FROM public.stakeholder_decision_outcome AS outcome
                JOIN public.stakeholder_decision AS decision ON decision.id = outcome.decision_id
                 WHERE outcome.id = requested_entity
                   AND decision.scope_type = 'location' AND decision.scope_id = requested_location_id
            )) OR (requested_entity_type = 'stakeholder_engagement_outcome' AND EXISTS (
                SELECT 1 FROM public.stakeholder_engagement_outcome AS outcome
                JOIN public.stakeholder_engagement_plan AS plan ON plan.id = outcome.plan_id
                 WHERE outcome.id = requested_entity
                   AND plan.scope_type = 'location' AND plan.scope_id = requested_location_id
            ))
        ) THEN
            RAISE EXCEPTION 'linked record was not found in this location'
                USING ERRCODE = 'P0002';
        END IF;
        INSERT INTO public.governance_tension_link AS tension_link (
            tension_id, link_type, entity_type, entity_id, summary, created_by_party_id
        ) VALUES (
            requested_tension_id, requested_link_type, requested_entity_type, requested_entity,
            NULLIF(BTRIM(requested_content ->> 'summary'), ''), actor_party
        )
        ON CONFLICT ON CONSTRAINT governance_tension_link_action_identity_key DO UPDATE
            SET summary = EXCLUDED.summary, created_by_party_id = EXCLUDED.created_by_party_id
        RETURNING tension_link.id INTO event_link_id;
        UPDATE public.governance_tension AS tension
           SET updated_at = clock_timestamp()
         WHERE tension.id = requested_tension_id
         RETURNING tension.updated_at INTO action_time;
        next_status := tension_record.status;
        event_action := 'linked';
    ELSIF requested_action = 'link_work_item' THEN
        IF tension_record.status NOT IN ('triaged', 'in_progress', 'deferred') THEN
            RAISE EXCEPTION 'governance tension cannot attach a work item from its current state'
                USING ERRCODE = '55000';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM public.work_item AS item
             WHERE item.id = requested_work_item AND item.location_id = requested_location_id
        ) THEN
            RAISE EXCEPTION 'work item was not found in this location'
                USING ERRCODE = 'P0002';
        END IF;
        INSERT INTO public.governance_tension_link AS tension_link (
            tension_id, link_type, entity_type, entity_id, created_by_party_id
        ) VALUES (
            requested_tension_id, 'work_item', 'work_item', requested_work_item, actor_party
        )
        ON CONFLICT ON CONSTRAINT governance_tension_link_action_identity_key DO UPDATE
            SET created_by_party_id = EXCLUDED.created_by_party_id
        RETURNING tension_link.id INTO event_link_id;
        UPDATE public.governance_tension AS tension
           SET work_item_id = requested_work_item, status = 'in_progress', updated_at = clock_timestamp()
         WHERE tension.id = requested_tension_id
         RETURNING tension.updated_at INTO action_time;
        next_status := 'in_progress';
        event_action := 'linked_work_item';
    ELSIF requested_action = 'resolve' THEN
        IF tension_record.status NOT IN ('submitted', 'triaged', 'in_progress', 'deferred') THEN
            RAISE EXCEPTION 'governance tension cannot be resolved from its current state'
                USING ERRCODE = '55000';
        END IF;
        UPDATE public.governance_tension AS tension
           SET status = 'resolved',
               resolution_summary = BTRIM(requested_content ->> 'resolution_summary'),
               updated_at = clock_timestamp()
         WHERE tension.id = requested_tension_id
         RETURNING tension.updated_at INTO action_time;
        next_status := 'resolved';
        event_action := 'resolved';
    ELSE
        IF tension_record.status NOT IN ('submitted', 'triaged', 'in_progress') THEN
            RAISE EXCEPTION 'governance tension cannot be deferred from its current state'
                USING ERRCODE = '55000';
        END IF;
        UPDATE public.governance_tension AS tension
           SET status = 'deferred', deferred_until = requested_due,
               updated_at = clock_timestamp()
         WHERE tension.id = requested_tension_id
         RETURNING tension.updated_at INTO action_time;
        next_status := 'deferred';
        event_action := 'deferred';
    END IF;

    INSERT INTO public.governance_tension_event (
        tension_id, actor_party_id, from_status, to_status, action, note
    ) VALUES (
        requested_tension_id, actor_party, tension_record.status, next_status,
        event_action, normalized_reason
    );
    INSERT INTO public.governance_tension_action_request (
        operator_id, actor_party_id, location_id, tension_id, request_id, action,
        requested_content, reason, from_status, result_status, result_updated_at, link_id
    ) VALUES (
        context_record.actor_id, actor_party, requested_location_id, requested_tension_id,
        requested_request_id, requested_action, normalized_content, normalized_reason,
        tension_record.status, next_status, action_time, event_link_id
    );

    tension_id := requested_tension_id;
    action := requested_action;
    status := next_status;
    updated_at := action_time;
    request_id := requested_request_id;
    link_id := event_link_id;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.mutate_governance_tension_action(UUID, UUID, TEXT, UUID, JSONB, TEXT)
    OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.mutate_governance_tension_action(UUID, UUID, TEXT, UUID, JSONB, TEXT)
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.mutate_governance_tension_action(UUID, UUID, TEXT, UUID, JSONB, TEXT)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.governance_tension_action_request FROM kokonut_directus_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE public.governance_tension_action_request FROM kokonut_runtime;
    END IF;
END;
$$;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_governance_action_owner;

COMMENT ON TABLE public.governance_tension_action_request IS
    'Append-only idempotency and audit receipts for signed location-scoped governance tension actions; actor identity remains private.';
COMMENT ON FUNCTION kokonut_security.mutate_governance_tension_action(UUID, UUID, TEXT, UUID, JSONB, TEXT) IS
    'Applies one allowlisted, exact-location governance tension action under signed operator scope and records the lifecycle event plus replay receipt atomically.';

COMMIT;
