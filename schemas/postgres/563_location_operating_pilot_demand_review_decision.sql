-- Record one independent approve/reject decision for a submitted Kernel demand.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_demand_review_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reviewer_operator_id UUID NOT NULL
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL
        REFERENCES public.party(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL
        REFERENCES public.location(id) ON DELETE RESTRICT,
    signal_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_demand_signal(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (reviewer_operator_id, request_id),
    CHECK (reason IS NULL OR pg_catalog.char_length(reason) <= 2000),
    CHECK (
        decision <> 'rejected'
        OR NULLIF(pg_catalog.btrim(reason, ' ' || pg_catalog.chr(9) || pg_catalog.chr(10) || pg_catalog.chr(13)), '') IS NOT NULL
    )
);
REVOKE ALL ON TABLE public.operating_demand_review_decision FROM PUBLIC;
REVOKE ALL ON TABLE public.operating_demand_review_decision
    FROM kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT (
    reviewer_operator_id, reviewer_party_id, request_id, location_id,
    signal_id, decision, reason
)
ON TABLE public.operating_demand_review_decision
TO kokonut_operating_pilot_reader;
GRANT INSERT (
    reviewer_operator_id, reviewer_party_id, request_id, location_id,
    signal_id, decision, reason
)
ON TABLE public.operating_demand_review_decision
TO kokonut_operating_pilot_reader;

DO $$
DECLARE column_name TEXT;
        role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_operating_pilot_reader', 'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            IF role_name IN ('kokonut_runtime', 'kokonut_directus_runtime') THEN
                EXECUTE format(
                    'REVOKE INSERT, UPDATE, DELETE ON TABLE public.operating_demand_signal FROM %I',
                    role_name
                );
            END IF;
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
                IF role_name IN ('kokonut_runtime', 'kokonut_directus_runtime') THEN
                    EXECUTE format(
                        'REVOKE INSERT (%1$I) ON TABLE public.operating_demand_signal FROM %2$I',
                        column_name, role_name
                    );
                END IF;
            END LOOP;
        END IF;
    END LOOP;
    GRANT UPDATE (status) ON TABLE public.operating_demand_signal
        TO kokonut_operating_pilot_reader;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_operating_pilot_demand(
    requested_location_id UUID,
    requested_signal_id UUID,
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
        pg_catalog.btrim(requested_reason, ' ' || pg_catalog.chr(9) || pg_catalog.chr(10) || pg_catalog.chr(13)),
        ''
    );
    existing_decision RECORD;
    signal_record RECORD;
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
        RAISE EXCEPTION 'Demand review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Demand review requires an active exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL
       OR requested_decision NOT IN ('approved', 'rejected')
       OR requested_reason IS NOT NULL AND pg_catalog.char_length(requested_reason) > 2000
       OR requested_decision = 'rejected' AND normalized_reason IS NULL THEN
        RAISE EXCEPTION 'Demand review decision or reason is invalid'
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
        RAISE EXCEPTION 'Demand review requires exactly one active human-party binding'
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

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT decision.location_id, decision.signal_id, decision.decision, decision.reason
      INTO existing_decision
      FROM public.operating_demand_review_decision AS decision
     WHERE decision.reviewer_operator_id = context_record.actor_id
       AND decision.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_decision.location_id IS DISTINCT FROM requested_location_id
           OR existing_decision.signal_id IS DISTINCT FROM requested_signal_id
           OR existing_decision.decision IS DISTINCT FROM requested_decision
           OR existing_decision.reason IS DISTINCT FROM normalized_reason THEN
            RAISE EXCEPTION 'Demand review request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'signal_id', requested_signal_id,
            'status', existing_decision.decision,
            'decision', existing_decision.decision,
            'replayed', TRUE
        );
    END IF;

    SELECT signal.id, signal.created_by_party_id, signal.status
      INTO signal_record
      FROM public.operating_demand_signal AS signal
      JOIN public.operating_demand_draft_receipt AS draft
        ON draft.signal_id = signal.id
       AND draft.location_id = requested_location_id
     WHERE signal.id = requested_signal_id
       AND signal.scope_type = 'adelphi'
       AND signal.scope_id = pilot_scope_id
     FOR UPDATE OF signal;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submitted demand is unavailable for review'
            USING ERRCODE = '42501';
    END IF;
    IF signal_record.created_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Demand reviewers cannot review their own submissions'
            USING ERRCODE = '42501';
    END IF;
    IF signal_record.status <> 'submitted' THEN
        IF signal_record.status IN ('approved', 'rejected') THEN
            RAISE EXCEPTION 'Submitted demand already has a decision'
                USING ERRCODE = '23505';
        END IF;
        RAISE EXCEPTION 'Only submitted demand can be reviewed'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.operating_demand_signal
       SET status = requested_decision
     WHERE id = requested_signal_id AND status = 'submitted';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demand changed before review decision'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_demand_review_decision (
        reviewer_operator_id, reviewer_party_id, request_id, location_id,
        signal_id, decision, reason
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_request_id,
        requested_location_id, requested_signal_id, requested_decision,
        normalized_reason
    );

    RETURN pg_catalog.jsonb_build_object(
        'signal_id', requested_signal_id,
        'status', requested_decision,
        'decision', requested_decision,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.review_location_operating_pilot_demand(
    UUID, UUID, UUID, TEXT, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.review_location_operating_pilot_demand(
    UUID, UUID, UUID, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.review_location_operating_pilot_demand(
    UUID, UUID, UUID, TEXT, TEXT
) TO kokonut_runtime;

COMMENT ON FUNCTION kokonut_security.review_location_operating_pilot_demand(
    UUID, UUID, UUID, TEXT, TEXT
) IS
'Records an independent approve/reject decision for a receipt-backed submitted demand at the exact granted location; rejects self-review and preserves an append-only private decision receipt.';
COMMENT ON TABLE public.operating_demand_review_decision IS
'Private append-only reviewer decision and idempotency receipt for Kernel demand submissions; reasons are never returned by the Gateway.';

COMMIT;
