-- Revise only the caller's own unsubmitted operating resource-request draft.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_resource_request_draft_revision_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    original_draft_id UUID NOT NULL
        REFERENCES public.operating_resource_request_draft(id) ON DELETE RESTRICT,
    replacement_draft_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_resource_request_draft(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id),
    CHECK (original_draft_id <> replacement_draft_id)
);
REVOKE ALL ON TABLE public.operating_resource_request_draft_revision_receipt
    FROM PUBLIC, kokonut_operating_pilot_reader, kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT (operator_id, request_id, location_id, original_draft_id,
              replacement_draft_id, input_digest)
    ON TABLE public.operating_resource_request_draft_revision_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, request_id, location_id, original_draft_id,
              replacement_draft_id, input_digest)
    ON TABLE public.operating_resource_request_draft_revision_receipt
    TO kokonut_operating_pilot_reader;

REVOKE UPDATE ON TABLE public.operating_resource_request_draft
    FROM kokonut_operating_pilot_reader;
GRANT UPDATE (status, updated_at) ON TABLE public.operating_resource_request_draft
    TO kokonut_operating_pilot_reader;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.operating_resource_request_draft
    FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE ALL ON TABLE public.operating_resource_request_draft_revision_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.revise_location_operating_pilot_resource_draft(
    requested_location_id UUID,
    requested_draft_id UUID,
    requested_request_id UUID,
    requested_resource_type TEXT,
    requested_description TEXT,
    requested_urgency TEXT,
    requested_by DATE
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
    input_digest BYTEA;
    existing_revision RECORD;
    existing_status TEXT;
    old_draft RECORD;
    replacement_draft_id UUID;
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
        RAISE EXCEPTION 'Resource revision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'edit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Resource revision requires an active exact location edit-own grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_resource_type IS NULL
       OR requested_resource_type <> pg_catalog.btrim(requested_resource_type)
       OR pg_catalog.char_length(requested_resource_type) NOT BETWEEN 1 AND 50
       OR requested_resource_type !~ '^[A-Za-z0-9][A-Za-z0-9 _./-]{0,49}$'
       OR requested_description IS NULL
       OR requested_description <> pg_catalog.btrim(requested_description)
       OR pg_catalog.char_length(requested_description) NOT BETWEEN 1 AND 2000
       OR requested_urgency IS NULL
       OR requested_urgency NOT IN ('low', 'medium', 'high', 'critical')
       OR requested_by IS NULL THEN
        RAISE EXCEPTION 'Resource revision input is invalid or outside its bounds'
            USING ERRCODE = '22023';
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
        RAISE EXCEPTION 'Resource revision requires exactly one active human-party binding'
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

    input_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'draft_id', requested_draft_id,
            'resource_type', requested_resource_type,
            'description', requested_description,
            'urgency', requested_urgency,
            'requested_by', requested_by
        )::TEXT,
        'UTF8'
    ));
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.location_id, receipt.original_draft_id,
           receipt.replacement_draft_id, receipt.input_digest
      INTO existing_revision
      FROM public.operating_resource_request_draft_revision_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_revision.location_id IS DISTINCT FROM requested_location_id
           OR existing_revision.original_draft_id IS DISTINCT FROM requested_draft_id
           OR existing_revision.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Resource revision request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT draft.status
          INTO existing_status
          FROM public.operating_resource_request_draft AS draft
         WHERE draft.id = existing_revision.replacement_draft_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Resource revision receipt lost its replacement draft';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'draft_id', existing_revision.replacement_draft_id,
            'replaced_draft_id', existing_revision.original_draft_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.operating_resource_request_draft_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) THEN
        RAISE EXCEPTION 'Resource revision request ID conflicts with a create receipt'
            USING ERRCODE = '23505';
    END IF;

    SELECT draft.id, draft.status
      INTO old_draft
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
        RAISE EXCEPTION 'Resource draft is unavailable or no longer editable'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.operating_resource_request_draft
       SET status = 'superseded', updated_at = pg_catalog.clock_timestamp()
     WHERE id = old_draft.id AND status = 'draft';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Resource draft changed before revision'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_resource_request_draft (
        operator_id, location_id, scope_type, scope_id, requested_by_party_id,
        resource_type, description, urgency, requested_by
    ) VALUES (
        context_record.actor_id, requested_location_id, 'adelphi', pilot_scope_id,
        actor_party_id, requested_resource_type, requested_description,
        requested_urgency, requested_by
    ) RETURNING id INTO replacement_draft_id;

    -- Preserve the receipt-backed own-history projection for each version.
    INSERT INTO public.operating_resource_request_draft_receipt (
        operator_id, request_id, location_id, draft_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        replacement_draft_id, input_digest
    );
    INSERT INTO public.operating_resource_request_draft_revision_receipt (
        operator_id, request_id, location_id, original_draft_id,
        replacement_draft_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        old_draft.id, replacement_draft_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'draft_id', replacement_draft_id,
        'replaced_draft_id', old_draft.id,
        'status', 'draft',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.revise_location_operating_pilot_resource_draft(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, DATE
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.revise_location_operating_pilot_resource_draft(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, DATE
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.revise_location_operating_pilot_resource_draft(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, DATE
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.revise_location_operating_pilot_resource_draft(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, DATE
) FROM kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.revise_location_operating_pilot_resource_draft(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, DATE
) IS
'Revises only the signed operator own receipt-backed unsubmitted resource draft at the exact granted active Adelphi location; the old draft is retained as superseded and a private replacement draft is created without submission or review.';
COMMENT ON TABLE public.operating_resource_request_draft_revision_receipt IS
'Private idempotency and revision-link receipt for operator edits to own resource-request drafts; excludes request text and values.';

COMMIT;
