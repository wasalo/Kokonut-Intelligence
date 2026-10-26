-- Submit only an owner's receipt-backed learning-plan draft for review.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_pilot_learning_plan_submission_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    learning_plan_id UUID NOT NULL
        REFERENCES public.operating_learning_plan(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_pilot_learning_plan_submission_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
REVOKE ALL (
    operator_id, request_id, location_id, learning_plan_id, created_at
) ON TABLE public.operating_pilot_learning_plan_submission_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT (operator_id, request_id, location_id, learning_plan_id),
      INSERT (operator_id, request_id, location_id, learning_plan_id)
    ON TABLE public.operating_pilot_learning_plan_submission_receipt
    TO kokonut_operating_pilot_reader;

REVOKE UPDATE ON TABLE public.operating_learning_plan
    FROM kokonut_operating_pilot_reader;
REVOKE ALL ON TABLE public.operating_learning_plan
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
REVOKE ALL (
    id, party_id, scope_type, scope_id, title, competency_goals,
    support_requested, target_date, status, created_by_party_id,
    created_at, updated_at
) ON TABLE public.operating_learning_plan
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
GRANT UPDATE (title, competency_goals, support_requested, target_date, status, updated_at)
    ON TABLE public.operating_learning_plan TO kokonut_operating_pilot_reader;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_operating_pilot_learning_plan(
    requested_location_id UUID,
    requested_learning_plan_id UUID,
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
    actor_party_ids UUID[] := ARRAY[]::UUID[];
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
       OR requested_location_id IS NULL
       OR requested_learning_plan_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Learning-plan submission requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'submit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan submission requires an active exact location submit-own grant'
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
        actor_party_ids := pg_catalog.array_append(actor_party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(actor_party_ids) <> 1 THEN
        RAISE EXCEPTION 'Learning-plan submission requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    actor_party_id := actor_party_ids[1];

    SELECT scope.scope_id
      INTO pilot_scope_id
      FROM public.operating_pilot_scope AS scope
      JOIN public.farm AS pilot_farm
        ON pilot_farm.id = scope.scope_id
       AND pilot_farm.location_id = requested_location_id
       AND pilot_farm.status = 'active'
     WHERE scope.scope_type = 'adelphi'
       AND scope.status = 'active'
     ORDER BY scope.id
     LIMIT 1
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

    SELECT receipt.location_id, receipt.learning_plan_id
      INTO existing_receipt
      FROM public.operating_pilot_learning_plan_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.learning_plan_id IS DISTINCT FROM requested_learning_plan_id THEN
            RAISE EXCEPTION 'Learning-plan submission request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT plan.status
          INTO existing_status
          FROM public.operating_learning_plan AS plan
         WHERE plan.id = existing_receipt.learning_plan_id
           AND plan.party_id = actor_party_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Learning-plan submission receipt lost its plan';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'learning_plan_id', existing_receipt.learning_plan_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.operating_pilot_learning_plan_draft_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) OR EXISTS (
        SELECT 1 FROM public.operating_pilot_learning_plan_revision_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan submission request ID conflicts with another operation'
            USING ERRCODE = '23505';
    END IF;

    PERFORM plan.id
      FROM public.operating_pilot_learning_plan_draft_receipt AS draft_receipt
      JOIN public.operating_learning_plan AS plan
        ON plan.id = draft_receipt.learning_plan_id
     WHERE draft_receipt.operator_id = context_record.actor_id
       AND draft_receipt.location_id = requested_location_id
       AND draft_receipt.learning_plan_id = requested_learning_plan_id
       AND plan.party_id = actor_party_id
       AND plan.scope_type = 'adelphi'
       AND plan.scope_id = pilot_scope_id
       AND plan.status = 'draft'
     FOR UPDATE OF plan;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Learning-plan draft is unavailable or no longer submittable'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.operating_learning_plan
       SET status = 'submitted', updated_at = pg_catalog.clock_timestamp()
     WHERE id = requested_learning_plan_id AND status = 'draft';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Learning-plan draft changed before submission'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_pilot_learning_plan_submission_receipt (
        operator_id, request_id, location_id, learning_plan_id
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_learning_plan_id
    );

    RETURN pg_catalog.jsonb_build_object(
        'learning_plan_id', requested_learning_plan_id,
        'status', 'submitted',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.submit_location_operating_pilot_learning_plan(
    UUID, UUID, UUID
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_operating_pilot_learning_plan(
    UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_operating_pilot_learning_plan(
    UUID, UUID, UUID
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_operating_pilot_learning_plan(
    UUID, UUID, UUID
) FROM kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.submit_location_operating_pilot_learning_plan(
    UUID, UUID, UUID
) IS 'Submits only the signed operator own receipt-backed learning-plan draft at the exact granted location; independent review and any activation remain separate.';
COMMENT ON TABLE public.operating_pilot_learning_plan_submission_receipt IS
'Private append-only idempotency receipt for submitting an own learning-plan draft; contains no plan content.';

COMMIT;
