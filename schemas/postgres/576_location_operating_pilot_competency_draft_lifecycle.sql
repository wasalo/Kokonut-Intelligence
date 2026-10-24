-- Allow operators to revise their own competency drafts and submit them for review.

BEGIN;

ALTER TABLE public.operating_pilot_competency_draft
    DROP CONSTRAINT IF EXISTS operating_pilot_competency_draft_status_check;
ALTER TABLE public.operating_pilot_competency_draft
    ADD CONSTRAINT operating_pilot_competency_draft_status_check
    CHECK (status IN ('draft', 'superseded', 'submitted', 'rejected', 'verified'));

CREATE TABLE IF NOT EXISTS public.operating_pilot_competency_revision_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    prior_draft_id UUID NOT NULL
        REFERENCES public.operating_pilot_competency_draft(id) ON DELETE RESTRICT,
    replacement_draft_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_pilot_competency_draft(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.operating_pilot_competency_submission_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    draft_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_pilot_competency_draft(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

REVOKE ALL ON TABLE public.operating_pilot_competency_revision_receipt,
    public.operating_pilot_competency_submission_receipt FROM PUBLIC;
GRANT SELECT (
    id, operator_id, location_id, scope_id, party_id, competency_key,
    current_level, target_level, evidence_note, status
) ON TABLE public.operating_pilot_competency_draft TO kokonut_operating_pilot_reader;
GRANT UPDATE (status, updated_at)
    ON TABLE public.operating_pilot_competency_draft TO kokonut_operating_pilot_reader;
GRANT INSERT (
    operator_id, location_id, scope_id, party_id, competency_key,
    current_level, target_level, evidence_note
) ON TABLE public.operating_pilot_competency_draft TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, prior_draft_id,
              replacement_draft_id, input_digest),
      INSERT (operator_id, request_id, location_id, prior_draft_id,
              replacement_draft_id, input_digest)
    ON TABLE public.operating_pilot_competency_revision_receipt
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, draft_id),
      INSERT (operator_id, request_id, location_id, draft_id)
    ON TABLE public.operating_pilot_competency_submission_receipt
    TO kokonut_operating_pilot_reader;

CREATE OR REPLACE FUNCTION kokonut_security.revise_location_operating_pilot_competency_draft(
    requested_location_id UUID,
    requested_draft_id UUID,
    requested_request_id UUID,
    requested_competency_key TEXT,
    requested_current_level NUMERIC,
    requested_target_level NUMERIC,
    requested_evidence_note TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    active_parties UUID[] := ARRAY[]::UUID[];
    binding_record RECORD;
    actor_party_id UUID;
    pilot_scope_id UUID;
    normalized_key TEXT;
    normalized_note TEXT;
    input_digest BYTEA;
    existing_receipt RECORD;
    existing_status TEXT;
    replacement_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_draft_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Competency revision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'edit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Competency revision requires an exact location edit-own grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_key := pg_catalog.lower(pg_catalog.btrim(requested_competency_key));
    normalized_note := NULLIF(pg_catalog.btrim(requested_evidence_note), '');
    IF requested_competency_key IS NULL OR normalized_key IS NULL
       OR normalized_key !~ '^[a-z][a-z0-9_.-]{0,119}$'
       OR requested_current_level IS NULL
       OR requested_current_level NOT BETWEEN 0 AND 5
       OR pg_catalog.scale(requested_current_level) > 2
       OR requested_target_level IS NULL
       OR requested_target_level NOT BETWEEN requested_current_level AND 5
       OR pg_catalog.scale(requested_target_level) > 2
       OR requested_evidence_note IS NOT NULL
          AND pg_catalog.char_length(requested_evidence_note) > 2000 THEN
        RAISE EXCEPTION 'Competency revision input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    FOR binding_record IN
        SELECT binding.party_id
          FROM public.operator_governance_party_binding AS binding
          JOIN public.operator_identity AS operator
            ON operator.id = binding.operator_id AND operator.enabled
          JOIN public.party AS actor
            ON actor.id = binding.party_id
           AND actor.party_type = 'person' AND actor.status = 'active'
         WHERE binding.operator_id = context_record.actor_id
           AND binding.revoked_at IS NULL
         FOR SHARE OF binding, operator, actor
    LOOP
        active_parties := pg_catalog.array_append(active_parties, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(active_parties) <> 1 THEN
        RAISE EXCEPTION 'Competency revision requires one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    actor_party_id := active_parties[1];

    SELECT scope.scope_id INTO pilot_scope_id
      FROM public.operating_pilot_scope AS scope
      JOIN public.farm AS pilot_farm
        ON pilot_farm.id = scope.scope_id
       AND pilot_farm.location_id = requested_location_id
       AND pilot_farm.status = 'active'
     WHERE scope.scope_type = 'adelphi' AND scope.status = 'active'
     FOR KEY SHARE OF scope, pilot_farm;
    IF pilot_scope_id IS NULL THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    input_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'prior_draft_id', requested_draft_id,
            'competency_key', normalized_key,
            'current_level', requested_current_level,
            'target_level', requested_target_level,
            'evidence_note', normalized_note
        )::TEXT, 'UTF8'
    ));
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
    ));

    SELECT receipt.location_id, receipt.prior_draft_id,
           receipt.replacement_draft_id, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_pilot_competency_revision_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.prior_draft_id IS DISTINCT FROM requested_draft_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Competency revision request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT draft.status INTO existing_status
          FROM public.operating_pilot_competency_draft AS draft
         WHERE draft.id = existing_receipt.replacement_draft_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Competency revision receipt lost its replacement draft';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'draft_id', existing_receipt.replacement_draft_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    PERFORM draft.id
      FROM public.operating_pilot_competency_draft AS draft
     WHERE draft.id = requested_draft_id
       AND draft.operator_id = context_record.actor_id
       AND draft.location_id = requested_location_id
       AND draft.scope_id = pilot_scope_id
       AND draft.party_id = actor_party_id
       AND draft.status IN ('draft', 'rejected')
       AND EXISTS (
           SELECT 1 FROM public.operating_pilot_competency_draft_receipt AS receipt
            WHERE receipt.operator_id = draft.operator_id
              AND receipt.location_id = draft.location_id
              AND receipt.draft_id = draft.id
       )
     FOR UPDATE OF draft;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Competency draft is unavailable or cannot be revised'
            USING ERRCODE = '42501';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.operating_pilot_competency_draft AS draft
         WHERE draft.operator_id = context_record.actor_id
           AND draft.location_id = requested_location_id
           AND draft.competency_key = normalized_key
           AND draft.status = 'draft'
           AND draft.id <> requested_draft_id
    ) THEN
        RAISE EXCEPTION 'An open draft already exists for this competency'
            USING ERRCODE = '23505';
    END IF;

    UPDATE public.operating_pilot_competency_draft
       SET status = 'superseded', updated_at = clock_timestamp()
     WHERE id = requested_draft_id AND status IN ('draft', 'rejected');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Competency draft changed before revision'
            USING ERRCODE = '40001';
    END IF;
    INSERT INTO public.operating_pilot_competency_draft (
        operator_id, location_id, scope_id, party_id, competency_key,
        current_level, target_level, evidence_note
    ) VALUES (
        context_record.actor_id, requested_location_id, pilot_scope_id,
        actor_party_id, normalized_key, requested_current_level,
        requested_target_level, normalized_note
    ) RETURNING id INTO replacement_id;
    INSERT INTO public.operating_pilot_competency_revision_receipt (
        operator_id, request_id, location_id, prior_draft_id,
        replacement_draft_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_draft_id, replacement_id, input_digest
    );
    INSERT INTO public.operating_pilot_competency_draft_receipt (
        operator_id, request_id, location_id, draft_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        replacement_id, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'draft_id', replacement_id, 'status', 'draft', 'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.revise_location_operating_pilot_competency_draft(
    UUID, UUID, UUID, TEXT, NUMERIC, NUMERIC, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.revise_location_operating_pilot_competency_draft(
    UUID, UUID, UUID, TEXT, NUMERIC, NUMERIC, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.revise_location_operating_pilot_competency_draft(
    UUID, UUID, UUID, TEXT, NUMERIC, NUMERIC, TEXT
) TO kokonut_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_operating_pilot_competency_draft(
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
    active_parties UUID[] := ARRAY[]::UUID[];
    binding_record RECORD;
    actor_party_id UUID;
    pilot_scope_id UUID;
    existing_receipt RECORD;
    existing_status TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_draft_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Competency submission requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'submit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Competency submission requires an exact location submit-own grant'
            USING ERRCODE = '42501';
    END IF;

    FOR binding_record IN
        SELECT binding.party_id
          FROM public.operator_governance_party_binding AS binding
          JOIN public.operator_identity AS operator
            ON operator.id = binding.operator_id AND operator.enabled
          JOIN public.party AS actor
            ON actor.id = binding.party_id
           AND actor.party_type = 'person' AND actor.status = 'active'
         WHERE binding.operator_id = context_record.actor_id
           AND binding.revoked_at IS NULL
         FOR SHARE OF binding, operator, actor
    LOOP
        active_parties := pg_catalog.array_append(active_parties, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(active_parties) <> 1 THEN
        RAISE EXCEPTION 'Competency submission requires one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    actor_party_id := active_parties[1];

    SELECT scope.scope_id INTO pilot_scope_id
      FROM public.operating_pilot_scope AS scope
      JOIN public.farm AS pilot_farm
        ON pilot_farm.id = scope.scope_id
       AND pilot_farm.location_id = requested_location_id
       AND pilot_farm.status = 'active'
     WHERE scope.scope_type = 'adelphi' AND scope.status = 'active'
     FOR KEY SHARE OF scope, pilot_farm;
    IF pilot_scope_id IS NULL THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
    ));
    SELECT receipt.location_id, receipt.draft_id
      INTO existing_receipt
      FROM public.operating_pilot_competency_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.draft_id IS DISTINCT FROM requested_draft_id THEN
            RAISE EXCEPTION 'Competency submission request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT draft.status INTO existing_status
          FROM public.operating_pilot_competency_draft AS draft
         WHERE draft.id = existing_receipt.draft_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Competency submission receipt lost its draft';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'draft_id', existing_receipt.draft_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    PERFORM draft.id
      FROM public.operating_pilot_competency_draft AS draft
     WHERE draft.id = requested_draft_id
       AND draft.operator_id = context_record.actor_id
       AND draft.location_id = requested_location_id
       AND draft.scope_id = pilot_scope_id
       AND draft.party_id = actor_party_id
       AND draft.status = 'draft'
       AND EXISTS (
           SELECT 1 FROM public.operating_pilot_competency_draft_receipt AS receipt
            WHERE receipt.operator_id = draft.operator_id
              AND receipt.location_id = draft.location_id
              AND receipt.draft_id = draft.id
       )
     FOR UPDATE OF draft;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Competency draft is unavailable or no longer submittable'
            USING ERRCODE = '42501';
    END IF;
    UPDATE public.operating_pilot_competency_draft
       SET status = 'submitted', updated_at = clock_timestamp()
     WHERE id = requested_draft_id AND status = 'draft';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Competency draft changed before submission'
            USING ERRCODE = '40001';
    END IF;
    INSERT INTO public.operating_pilot_competency_submission_receipt (
        operator_id, request_id, location_id, draft_id
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_draft_id
    );
    RETURN pg_catalog.jsonb_build_object(
        'draft_id', requested_draft_id, 'status', 'submitted', 'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.submit_location_operating_pilot_competency_draft(
    UUID, UUID, UUID
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_operating_pilot_competency_draft(
    UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_operating_pilot_competency_draft(
    UUID, UUID, UUID
) TO kokonut_runtime;

REVOKE ALL ON TABLE public.operating_pilot_competency_draft,
    public.operating_pilot_competency_draft_receipt,
    public.operating_pilot_competency_revision_receipt,
    public.operating_pilot_competency_submission_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.revise_location_operating_pilot_competency_draft(
    UUID, UUID, UUID, TEXT, NUMERIC, NUMERIC, TEXT
) IS 'Supersedes and replaces only the authenticated operator own receipt-backed draft or rejected competency assessment at the exact location; prior records remain retained.';
COMMENT ON FUNCTION kokonut_security.submit_location_operating_pilot_competency_draft(
    UUID, UUID, UUID
) IS 'Submits only the authenticated operator own receipt-backed draft for independent review; no verification or approval is performed.';

COMMIT;
