-- Record one independent approve/reject decision for a Kernel resource request.

BEGIN;

-- Some populated legacy installations created this table before reviewer
-- attribution was added to the canonical schema. Keep the decision path
-- upgrade-safe without rewriting or backfilling historical decisions.
ALTER TABLE public.operating_resource_request
    ADD COLUMN IF NOT EXISTS decided_by_party_id UUID
        REFERENCES public.party(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS public.operating_resource_request_review_decision (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    reviewer_operator_id UUID NOT NULL
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL
        REFERENCES public.party(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL
        REFERENCES public.location(id) ON DELETE RESTRICT,
    resource_request_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_resource_request(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reason TEXT,
    input_digest BYTEA NOT NULL
        CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (reviewer_operator_id, request_id),
    CHECK (reason IS NULL OR pg_catalog.char_length(reason) <= 2000),
    CHECK (
        decision <> 'rejected'
        OR NULLIF(
            pg_catalog.btrim(
                reason,
                ' ' || pg_catalog.chr(9) || pg_catalog.chr(10) || pg_catalog.chr(13)
            ),
            ''
        ) IS NOT NULL
    )
);
REVOKE ALL ON TABLE public.operating_resource_request_review_decision FROM PUBLIC;
REVOKE ALL ON TABLE public.operating_resource_request_review_decision
    FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE ALL ON TABLE public.operating_resource_request_review_decision
    FROM kokonut_operating_pilot_reader;
GRANT SELECT (
    reviewer_operator_id, reviewer_party_id, request_id, location_id,
    resource_request_id, decision, reason, input_digest
)
ON TABLE public.operating_resource_request_review_decision
TO kokonut_operating_pilot_reader;
GRANT INSERT (
    reviewer_operator_id, reviewer_party_id, request_id, location_id,
    resource_request_id, decision, reason, input_digest
)
ON TABLE public.operating_resource_request_review_decision
TO kokonut_operating_pilot_reader;

GRANT UPDATE (
    decision, decision_reason, decided_by_party_id, decided_at, status, updated_at
)
ON TABLE public.operating_resource_request
TO kokonut_operating_pilot_reader;

DO $$
DECLARE
    role_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_resource_request_review_decision FROM %I',
                role_name
            );
            EXECUTE format(
                'REVOKE UPDATE ON TABLE public.operating_resource_request FROM %I', role_name
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.operating_resource_request'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.operating_resource_request FROM %2$I',
                    column_name, role_name
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_operating_pilot_resource_request(
    requested_location_id UUID,
    requested_resource_request_id UUID,
    requested_request_id UUID,
    requested_decision TEXT,
    requested_reason TEXT
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
    reviewer_party_id UUID;
    pilot_scope_id UUID;
    normalized_reason TEXT := NULLIF(
        pg_catalog.btrim(
            requested_reason,
            ' ' || pg_catalog.chr(9) || pg_catalog.chr(10) || pg_catalog.chr(13)
        ),
        ''
    );
    input_digest BYTEA;
    existing_decision RECORD;
    request_record RECORD;
    canonical_decision TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_resource_request_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Resource review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Resource review requires an active exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL
       OR requested_decision NOT IN ('approved', 'rejected')
       OR requested_reason IS NOT NULL AND pg_catalog.char_length(requested_reason) > 2000
       OR requested_decision = 'rejected' AND normalized_reason IS NULL THEN
        RAISE EXCEPTION 'Resource review decision or reason is invalid'
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
    IF coalesce(pg_catalog.cardinality(active_party_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Resource review requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    reviewer_party_id := active_party_ids[1];

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

    canonical_decision := CASE requested_decision
        WHEN 'approved' THEN 'approved'
        WHEN 'rejected' THEN 'declined'
    END;
    input_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'resource_request_id', requested_resource_request_id,
            'decision', requested_decision,
            'reason', normalized_reason
        )::TEXT,
        'UTF8'
    ));

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT decision.location_id, decision.resource_request_id,
           decision.decision, decision.reason, decision.input_digest
      INTO existing_decision
      FROM public.operating_resource_request_review_decision AS decision
     WHERE decision.reviewer_operator_id = context_record.actor_id
       AND decision.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_decision.location_id IS DISTINCT FROM requested_location_id
           OR existing_decision.resource_request_id IS DISTINCT FROM requested_resource_request_id
           OR existing_decision.decision IS DISTINCT FROM requested_decision
           OR existing_decision.reason IS DISTINCT FROM normalized_reason
           OR existing_decision.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Resource review request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'resource_request_id', requested_resource_request_id,
            'status', 'reviewed',
            'decision', existing_decision.decision,
            'replayed', TRUE
        );
    END IF;

    SELECT request.id, request.requested_by_party_id, request.scope_id,
           request.status, request.decision
      INTO request_record
      FROM public.operating_resource_request AS request
      JOIN public.operating_resource_request_draft_submission_receipt AS submission
        ON submission.resource_request_id = request.id
       AND submission.location_id = requested_location_id
      JOIN public.operating_resource_request_draft AS draft
        ON draft.id = submission.draft_id
       AND draft.operator_id = submission.operator_id
       AND draft.location_id = requested_location_id
       AND draft.status = 'submitted'
       AND draft.submitted_request_id = request.id
     WHERE request.id = requested_resource_request_id
       AND request.scope_type = 'adelphi'
       AND request.scope_id = pilot_scope_id
     FOR UPDATE OF request, draft;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Receipt-backed resource request is unavailable for review'
            USING ERRCODE = '42501';
    END IF;
    IF request_record.requested_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Resource reviewers cannot review their own submissions'
            USING ERRCODE = '42501';
    END IF;
    IF request_record.status <> 'submitted' OR request_record.decision <> 'pending' THEN
        RAISE EXCEPTION 'Only pending submitted resource requests can be reviewed'
            USING ERRCODE = '23505';
    END IF;

    UPDATE public.operating_resource_request
       SET status = 'reviewed',
           decision = canonical_decision,
           decision_reason = normalized_reason,
           decided_by_party_id = reviewer_party_id,
           decided_at = pg_catalog.clock_timestamp(),
           updated_at = pg_catalog.clock_timestamp()
     WHERE id = requested_resource_request_id
       AND scope_id = pilot_scope_id
       AND status = 'submitted'
       AND decision = 'pending';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Resource request changed before review decision'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_resource_request_review_decision (
        reviewer_operator_id, reviewer_party_id, request_id, location_id,
        resource_request_id, decision, reason, input_digest
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_request_id,
        requested_location_id, requested_resource_request_id, requested_decision,
        normalized_reason, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'resource_request_id', requested_resource_request_id,
        'status', 'reviewed',
        'decision', requested_decision,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.review_location_operating_pilot_resource_request(
    UUID, UUID, UUID, TEXT, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.review_location_operating_pilot_resource_request(
    UUID, UUID, UUID, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.review_location_operating_pilot_resource_request(
    UUID, UUID, UUID, TEXT, TEXT
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.review_location_operating_pilot_resource_request(
    UUID, UUID, UUID, TEXT, TEXT
) FROM kokonut_directus_runtime;

COMMENT ON TABLE public.operating_resource_request_review_decision IS
'Private append-only idempotency and audit record for an independent human decision on a receipt-backed Kernel resource request. Fulfillment remains separate.';
COMMENT ON FUNCTION kokonut_security.review_location_operating_pilot_resource_request(
    UUID, UUID, UUID, TEXT, TEXT
) IS
'Records one exact-location independent approve/reject decision for a submitted Kernel resource request, excludes self-review and legacy rows, and does not fulfill or partially allocate resources.';

COMMIT;
