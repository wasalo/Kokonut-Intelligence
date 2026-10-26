-- Submit only the caller's own private operating demand draft for review.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_demand_draft_submission_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    signal_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_demand_signal(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_demand_draft_submission_receipt FROM PUBLIC;
GRANT SELECT (operator_id, request_id, location_id, signal_id)
    ON TABLE public.operating_demand_draft_submission_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, request_id, location_id, signal_id)
    ON TABLE public.operating_demand_draft_submission_receipt
    TO kokonut_operating_pilot_reader;

GRANT SELECT (id, scope_type, scope_id, status, created_by_party_id)
    ON TABLE public.operating_demand_signal TO kokonut_operating_pilot_reader;

DO $$
DECLARE role_name TEXT;
        column_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_operating_pilot_reader', 'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE UPDATE ON TABLE public.operating_demand_signal FROM %I', role_name
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.operating_demand_signal'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.operating_demand_signal FROM %2$I',
                    column_name, role_name
                );
            END LOOP;
        END IF;
    END LOOP;
    GRANT UPDATE (status) ON TABLE public.operating_demand_signal
        TO kokonut_operating_pilot_reader;

    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_demand_draft_submission_receipt FROM %I',
                role_name
            );
            EXECUTE format(
                'REVOKE INSERT, UPDATE, DELETE ON TABLE public.operating_demand_signal FROM %I',
                role_name
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.operating_demand_signal'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I) ON TABLE public.operating_demand_signal FROM %2$I',
                    column_name, role_name
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_operating_pilot_demand_draft(
    requested_location_id UUID,
    requested_signal_id UUID,
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
    existing_status TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_signal_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Demand submission requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'submit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Demand submission requires an active exact location submit-own grant'
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
        RAISE EXCEPTION 'Demand submission requires exactly one active human-party binding'
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

    SELECT receipt.location_id, receipt.signal_id
      INTO existing_receipt
      FROM public.operating_demand_draft_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.signal_id IS DISTINCT FROM requested_signal_id THEN
            RAISE EXCEPTION 'Demand submission request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT signal.status
          INTO existing_status
          FROM public.operating_demand_signal AS signal
         WHERE signal.id = existing_receipt.signal_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Demand submission receipt lost its signal';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'signal_id', existing_receipt.signal_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    SELECT signal.id, signal.status
      INTO existing_receipt
      FROM public.operating_demand_draft_receipt AS draft
      JOIN public.operating_demand_signal AS signal
        ON signal.id = draft.signal_id
     WHERE draft.operator_id = context_record.actor_id
       AND draft.location_id = requested_location_id
       AND draft.signal_id = requested_signal_id
       AND signal.scope_type = 'adelphi'
       AND signal.scope_id = pilot_scope_id
       AND signal.created_by_party_id = actor_party_id
     FOR UPDATE OF signal;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demand draft is unavailable or not owned by this operator'
            USING ERRCODE = '42501';
    END IF;
    IF existing_receipt.status <> 'draft' THEN
        RAISE EXCEPTION 'Demand draft has already left the draft state'
            USING ERRCODE = '23505';
    END IF;

    UPDATE public.operating_demand_signal
       SET status = 'submitted'
     WHERE id = requested_signal_id AND status = 'draft';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demand draft changed before submission'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_demand_draft_submission_receipt (
        operator_id, request_id, location_id, signal_id
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_signal_id
    );

    RETURN pg_catalog.jsonb_build_object(
        'signal_id', requested_signal_id,
        'status', 'submitted',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.submit_location_operating_pilot_demand_draft(
    UUID, UUID, UUID
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_operating_pilot_demand_draft(
    UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_operating_pilot_demand_draft(
    UUID, UUID, UUID
) TO kokonut_runtime;

COMMENT ON FUNCTION kokonut_security.submit_location_operating_pilot_demand_draft(
    UUID, UUID, UUID
) IS
'Submits only the authenticated operator own private planning demand draft at the exact granted location; exact retries replay and independent review or fulfillment remains separate.';
COMMENT ON TABLE public.operating_demand_draft_submission_receipt IS
'Private idempotency receipt for submitting an own operating demand draft; contains no demand text or values.';

COMMIT;
