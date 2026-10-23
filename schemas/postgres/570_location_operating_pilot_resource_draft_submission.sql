-- Submit only the caller's own private resource-request draft for review.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_resource_request_draft_submission_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    draft_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_resource_request_draft(id) ON DELETE RESTRICT,
    resource_request_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_resource_request(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_resource_request_draft_submission_receipt
    FROM PUBLIC, kokonut_operating_pilot_reader, kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT (operator_id, request_id, location_id, draft_id, resource_request_id)
    ON TABLE public.operating_resource_request_draft_submission_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, request_id, location_id, draft_id, resource_request_id)
    ON TABLE public.operating_resource_request_draft_submission_receipt
    TO kokonut_operating_pilot_reader;

REVOKE INSERT, UPDATE, DELETE ON TABLE public.operating_resource_request
    FROM kokonut_operating_pilot_reader;
GRANT SELECT (id) ON TABLE public.operating_resource_request
    TO kokonut_operating_pilot_reader;
GRANT INSERT (scope_type, scope_id, requested_by_party_id, resource_type,
              description, urgency, requested_by, decision, status)
    ON TABLE public.operating_resource_request
    TO kokonut_operating_pilot_reader;

DO $$
DECLARE role_name TEXT;
        column_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_resource_request FROM %I', role_name
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.operating_resource_request'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.operating_resource_request FROM %2$I',
                    column_name, role_name
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

GRANT SELECT (submitted_request_id)
    ON TABLE public.operating_resource_request_draft TO kokonut_operating_pilot_reader;
REVOKE UPDATE ON TABLE public.operating_resource_request_draft
    FROM kokonut_operating_pilot_reader;
GRANT UPDATE (status, submitted_request_id, updated_at)
    ON TABLE public.operating_resource_request_draft
    TO kokonut_operating_pilot_reader;
REVOKE ALL ON TABLE public.operating_resource_request_draft_submission_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_operating_pilot_resource_draft(
    requested_location_id UUID,
    requested_draft_id UUID,
    requested_request_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    binding_record RECORD;
    active_party_ids UUID[] := ARRAY[]::UUID[];
    actor_party_id UUID;
    pilot_scope_id UUID;
    existing_receipt RECORD;
    existing_draft RECORD;
    existing_status TEXT;
    resource_request_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_draft_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Resource submission requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'submit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Resource submission requires an active exact location submit-own grant'
            USING ERRCODE = '42501';
    END IF;

    FOR binding_record IN
        SELECT binding.party_id
          FROM public.operator_governance_party_binding AS binding
          JOIN public.operator_identity AS operator
            ON operator.id = binding.operator_id AND operator.enabled
          JOIN public.party AS actor
            ON actor.id = binding.party_id
           AND actor.party_type = 'person'
           AND actor.status = 'active'
         WHERE binding.operator_id = context_record.actor_id
           AND binding.revoked_at IS NULL
         FOR SHARE OF binding, operator, actor
    LOOP
        active_party_ids := pg_catalog.array_append(active_party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(active_party_ids) <> 1 THEN
        RAISE EXCEPTION 'Resource submission requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    actor_party_id := active_party_ids[1];

    SELECT scope.scope_id
      INTO pilot_scope_id
      FROM public.operating_pilot_scope AS scope
      JOIN public.farm AS pilot_farm
        ON pilot_farm.id = scope.scope_id
       AND pilot_farm.location_id = requested_location_id
       AND pilot_farm.status = 'active'
     WHERE scope.scope_type = 'adelphi'
       AND scope.status = 'active'
     FOR KEY SHARE OF scope, pilot_farm;
    IF pilot_scope_id IS NULL THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.location_id, receipt.draft_id, receipt.resource_request_id
      INTO existing_receipt
      FROM public.operating_resource_request_draft_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.draft_id IS DISTINCT FROM requested_draft_id THEN
            RAISE EXCEPTION 'Resource submission request ID was reused for different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT draft.status, draft.submitted_request_id
          INTO existing_status, resource_request_id
          FROM public.operating_resource_request_draft AS draft
         WHERE draft.id = existing_receipt.draft_id
           AND draft.operator_id = context_record.actor_id
           AND draft.location_id = requested_location_id;
        IF existing_status IS DISTINCT FROM 'submitted'
           OR resource_request_id IS DISTINCT FROM existing_receipt.resource_request_id THEN
            RAISE EXCEPTION 'Resource submission receipt lost its linked submitted draft';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'draft_id', existing_receipt.draft_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.operating_resource_request_draft_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) OR EXISTS (
        SELECT 1
          FROM public.operating_resource_request_draft_revision_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) THEN
        RAISE EXCEPTION 'Resource submission request ID conflicts with another draft operation'
            USING ERRCODE = '23505';
    END IF;

    SELECT draft.id, draft.resource_type, draft.description, draft.urgency,
           draft.requested_by
      INTO existing_draft
      FROM public.operating_resource_request_draft_receipt AS original_receipt
      JOIN public.operating_resource_request_draft AS draft
        ON draft.id = original_receipt.draft_id
     WHERE original_receipt.operator_id = context_record.actor_id
       AND original_receipt.location_id = requested_location_id
       AND original_receipt.draft_id = requested_draft_id
       AND draft.operator_id = context_record.actor_id
       AND draft.location_id = requested_location_id
       AND draft.scope_type = 'adelphi'
       AND draft.scope_id = pilot_scope_id
       AND draft.requested_by_party_id = actor_party_id
       AND draft.status = 'draft'
     FOR UPDATE OF draft;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Resource draft is unavailable or no longer submittable'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.operating_resource_request (
        scope_type, scope_id, requested_by_party_id, resource_type, description,
        urgency, requested_by, decision, status
    ) VALUES (
        'adelphi', pilot_scope_id, actor_party_id, existing_draft.resource_type,
        existing_draft.description, existing_draft.urgency, existing_draft.requested_by,
        'pending', 'submitted'
    ) RETURNING id INTO resource_request_id;

    UPDATE public.operating_resource_request_draft
       SET status = 'submitted', submitted_request_id = resource_request_id,
           updated_at = pg_catalog.clock_timestamp()
     WHERE id = existing_draft.id AND status = 'draft';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Resource draft changed before submission'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_resource_request_draft_submission_receipt (
        operator_id, request_id, location_id, draft_id, resource_request_id
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        existing_draft.id, resource_request_id
    );

    RETURN pg_catalog.jsonb_build_object(
        'draft_id', existing_draft.id,
        'status', 'submitted',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.submit_location_operating_pilot_resource_draft(
    UUID, UUID, UUID
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_operating_pilot_resource_draft(
    UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_operating_pilot_resource_draft(
    UUID, UUID, UUID
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_operating_pilot_resource_draft(
    UUID, UUID, UUID
) FROM kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.submit_location_operating_pilot_resource_draft(
    UUID, UUID, UUID
) IS
'Submits only the authenticated operator own private resource-request draft at the exact granted location; it creates a pending legacy request, supports exact retries, and leaves independent review separate.';
COMMENT ON TABLE public.operating_resource_request_draft_submission_receipt IS
'Private idempotency receipt linking an own resource-request draft to its submitted canonical request; contains no request text or values.';

COMMIT;
