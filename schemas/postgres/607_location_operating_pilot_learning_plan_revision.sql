-- Revise only a caller's own receipt-backed, unsubmitted learning-plan draft.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_pilot_learning_plan_revision_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    learning_plan_id UUID NOT NULL
        REFERENCES public.operating_learning_plan(id) ON DELETE RESTRICT,
    expected_updated_at TIMESTAMPTZ NOT NULL,
    input_digest BYTEA NOT NULL CHECK (octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_pilot_learning_plan_revision_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT (operator_id, request_id, location_id, learning_plan_id,
              expected_updated_at, input_digest)
    ON TABLE public.operating_pilot_learning_plan_revision_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, request_id, location_id, learning_plan_id,
              expected_updated_at, input_digest)
    ON TABLE public.operating_pilot_learning_plan_revision_receipt
    TO kokonut_operating_pilot_reader;

REVOKE INSERT, UPDATE, DELETE ON TABLE public.operating_learning_plan
    FROM kokonut_operating_pilot_reader;
GRANT INSERT (
    id, party_id, scope_type, scope_id, title, competency_goals,
    support_requested, target_date, created_by_party_id, status
)
ON TABLE public.operating_learning_plan TO kokonut_operating_pilot_reader;
REVOKE UPDATE (title, competency_goals, support_requested, target_date, updated_at)
    ON TABLE public.operating_learning_plan FROM kokonut_operating_pilot_reader;
GRANT UPDATE (title, competency_goals, support_requested, target_date, updated_at)
    ON TABLE public.operating_learning_plan TO kokonut_operating_pilot_reader;
REVOKE ALL ON TABLE public.operating_learning_plan,
    public.operating_pilot_learning_plan_revision_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.revise_location_operating_pilot_learning_plan_draft(
    requested_location_id UUID,
    requested_learning_plan_id UUID,
    requested_request_id UUID,
    requested_expected_updated_at TIMESTAMPTZ,
    requested_title TEXT,
    requested_competency_goals JSONB,
    requested_support_requested JSONB,
    requested_target_date DATE
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    active_binding_count INTEGER;
    pilot_scope_id UUID;
    normalized_title TEXT;
    input_digest BYTEA;
    existing_receipt RECORD;
    existing_status TEXT;
    current_updated_at TIMESTAMPTZ;
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
        RAISE EXCEPTION 'Learning-plan revision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'edit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan revision requires an active exact location edit-own grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_title := NULLIF(pg_catalog.btrim(requested_title), '');
    IF normalized_title IS NULL
       OR pg_catalog.char_length(normalized_title) > 255
       OR requested_expected_updated_at IS NULL
       OR requested_competency_goals IS NULL
       OR pg_catalog.jsonb_typeof(requested_competency_goals) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_competency_goals) > 50
       OR requested_support_requested IS NULL
       OR pg_catalog.jsonb_typeof(requested_support_requested) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_support_requested) > 50
       OR pg_catalog.octet_length(requested_competency_goals::TEXT) > 8000
       OR pg_catalog.octet_length(requested_support_requested::TEXT) > 8000
       OR pg_catalog.octet_length(requested_competency_goals::TEXT)
          + pg_catalog.octet_length(requested_support_requested::TEXT) > 12000 THEN
        RAISE EXCEPTION 'Learning-plan revision input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     ORDER BY binding.id
     LIMIT 1
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Learning-plan revision requires an active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    SELECT count(*)::INTEGER INTO active_binding_count
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF active_binding_count <> 1 THEN
        RAISE EXCEPTION 'Learning-plan revision requires one unambiguous active human-party binding'
            USING ERRCODE = '42501';
    END IF;

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

    input_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'learning_plan_id', requested_learning_plan_id,
            'expected_updated_at', requested_expected_updated_at,
            'title', normalized_title,
            'competency_goals', requested_competency_goals,
            'support_requested', requested_support_requested,
            'target_date', requested_target_date
        )::TEXT,
        'UTF8'
    ));
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.location_id, receipt.learning_plan_id,
           receipt.expected_updated_at, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_pilot_learning_plan_revision_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.learning_plan_id IS DISTINCT FROM requested_learning_plan_id
           OR existing_receipt.expected_updated_at IS DISTINCT FROM requested_expected_updated_at
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Learning-plan revision request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT plan.status, plan.updated_at
          INTO existing_status, current_updated_at
          FROM public.operating_learning_plan AS plan
         WHERE plan.id = existing_receipt.learning_plan_id
           AND plan.party_id = actor_party_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Learning-plan revision receipt lost its plan';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'learning_plan_id', existing_receipt.learning_plan_id,
            'status', existing_status,
            'updated_at', current_updated_at,
            'replayed', TRUE
        );
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.operating_pilot_learning_plan_draft_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan revision request ID conflicts with a create receipt'
            USING ERRCODE = '23505';
    END IF;

    SELECT plan.status, plan.updated_at
      INTO existing_status, current_updated_at
      FROM public.operating_pilot_learning_plan_draft_receipt AS receipt
      JOIN public.operating_learning_plan AS plan
        ON plan.id = receipt.learning_plan_id
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.location_id = requested_location_id
       AND receipt.learning_plan_id = requested_learning_plan_id
       AND plan.party_id = actor_party_id
       AND plan.scope_type = 'adelphi'
       AND plan.scope_id = pilot_scope_id
       AND plan.status = 'draft'
     FOR UPDATE OF plan;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Learning-plan draft is unavailable or no longer editable'
            USING ERRCODE = '42501';
    END IF;
    IF current_updated_at IS DISTINCT FROM requested_expected_updated_at THEN
        RAISE EXCEPTION 'Learning-plan draft changed since it was loaded'
            USING ERRCODE = '40001';
    END IF;

    UPDATE public.operating_learning_plan AS plan
       SET title = normalized_title,
           competency_goals = requested_competency_goals,
           support_requested = requested_support_requested,
           target_date = requested_target_date,
           updated_at = pg_catalog.clock_timestamp()
     WHERE plan.id = requested_learning_plan_id
       AND plan.party_id = actor_party_id
       AND plan.scope_id = pilot_scope_id
       AND plan.status = 'draft'
    RETURNING plan.status, plan.updated_at INTO existing_status, current_updated_at;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Learning-plan draft changed before revision'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_pilot_learning_plan_revision_receipt (
        operator_id, request_id, location_id, learning_plan_id,
        expected_updated_at, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_learning_plan_id, requested_expected_updated_at, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'learning_plan_id', requested_learning_plan_id,
        'status', existing_status,
        'updated_at', current_updated_at,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.revise_location_operating_pilot_learning_plan_draft(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, JSONB, JSONB, DATE
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.revise_location_operating_pilot_learning_plan_draft(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, JSONB, JSONB, DATE
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.revise_location_operating_pilot_learning_plan_draft(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, JSONB, JSONB, DATE
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.revise_location_operating_pilot_learning_plan_draft(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, JSONB, JSONB, DATE
) FROM kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.revise_location_operating_pilot_learning_plan_draft(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, JSONB, JSONB, DATE
) IS 'Revises only a receipt-backed learning-plan draft owned by the signed operator person at its exact active Adelphi location; it does not submit or review the plan.';

COMMIT;
