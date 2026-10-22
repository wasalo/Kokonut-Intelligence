-- Revise only the caller's own unsubmitted operating demand draft.

BEGIN;

ALTER TABLE public.operating_demand_signal
    DROP CONSTRAINT IF EXISTS operating_demand_signal_status_check;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.operating_demand_signal'::REGCLASS
           AND conname = 'operating_demand_signal_status_lifecycle_check'
    ) THEN
        ALTER TABLE public.operating_demand_signal
            ADD CONSTRAINT operating_demand_signal_status_lifecycle_check
            CHECK (status IN ('draft', 'submitted', 'approved', 'rejected',
                              'fulfilled', 'cancelled', 'superseded'));
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.operating_demand_draft_revision_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    original_signal_id UUID NOT NULL
        REFERENCES public.operating_demand_signal(id) ON DELETE RESTRICT,
    replacement_signal_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_demand_signal(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id),
    CHECK (original_signal_id <> replacement_signal_id)
);
REVOKE ALL ON TABLE public.operating_demand_draft_revision_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.operating_demand_draft_revision_receipt
    FROM kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, original_signal_id,
              replacement_signal_id, input_digest)
    ON TABLE public.operating_demand_draft_revision_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, request_id, location_id, original_signal_id,
              replacement_signal_id, input_digest)
    ON TABLE public.operating_demand_draft_revision_receipt
    TO kokonut_operating_pilot_reader;

DO $$
DECLARE column_name TEXT;
        role_name TEXT;
BEGIN
    REVOKE UPDATE ON TABLE public.operating_demand_signal
        FROM kokonut_operating_pilot_reader;
    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = 'public.operating_demand_signal'::REGCLASS
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE format(
            'REVOKE UPDATE (%1$I) ON TABLE public.operating_demand_signal FROM kokonut_operating_pilot_reader',
            column_name
        );
    END LOOP;
    GRANT UPDATE (status) ON TABLE public.operating_demand_signal
        TO kokonut_operating_pilot_reader;

    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE INSERT, UPDATE, DELETE ON TABLE public.operating_demand_signal FROM %I',
                role_name
            );
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_demand_draft_revision_receipt FROM %I',
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

CREATE OR REPLACE FUNCTION kokonut_security.revise_location_operating_pilot_demand_draft(
    requested_location_id UUID,
    requested_signal_id UUID,
    requested_request_id UUID,
    requested_work_type TEXT,
    requested_period_start DATE,
    requested_period_end DATE,
    requested_required_hours NUMERIC,
    requested_priority TEXT,
    requested_description TEXT
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
    existing_receipt RECORD;
    existing_status TEXT;
    old_signal RECORD;
    replacement_signal_id UUID;
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
        RAISE EXCEPTION 'Demand revision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'edit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Demand revision requires an active exact location edit-own grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_work_type IS NULL
       OR requested_work_type <> pg_catalog.btrim(requested_work_type)
       OR pg_catalog.char_length(requested_work_type) NOT BETWEEN 1 AND 50
       OR requested_work_type !~ '^[[:alnum:]][[:alnum:] _./-]*$'
       OR requested_period_start IS NULL
       OR requested_period_end IS NULL
       OR requested_period_end < requested_period_start
       OR requested_period_end > requested_period_start + 366
       OR requested_required_hours IS NULL
       OR requested_required_hours <= 0
       OR requested_required_hours > 100000
       OR pg_catalog.scale(requested_required_hours) > 2
       OR requested_priority IS NULL
       OR requested_priority NOT IN ('low', 'medium', 'high', 'critical')
       OR requested_description IS NOT NULL
          AND pg_catalog.char_length(requested_description) > 2000 THEN
        RAISE EXCEPTION 'Demand revision input is invalid or outside its bounds'
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
        RAISE EXCEPTION 'Demand revision requires exactly one active human-party binding'
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
            'signal_id', requested_signal_id,
            'work_type', requested_work_type,
            'period_start', requested_period_start,
            'period_end', requested_period_end,
            'required_hours', requested_required_hours,
            'priority', requested_priority,
            'description', NULLIF(pg_catalog.btrim(requested_description), '')
        )::TEXT,
        'UTF8'
    ));

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.location_id, receipt.original_signal_id,
           receipt.replacement_signal_id, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_demand_draft_revision_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.original_signal_id IS DISTINCT FROM requested_signal_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Demand revision request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT signal.status
          INTO existing_status
          FROM public.operating_demand_signal AS signal
         WHERE signal.id = existing_receipt.replacement_signal_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Demand revision receipt lost its replacement signal';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'signal_id', existing_receipt.replacement_signal_id,
            'replaced_signal_id', existing_receipt.original_signal_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    SELECT signal.id, signal.status
      INTO old_signal
      FROM public.operating_demand_draft_receipt AS draft
      JOIN public.operating_demand_signal AS signal
        ON signal.id = draft.signal_id
     WHERE draft.operator_id = context_record.actor_id
       AND draft.location_id = requested_location_id
       AND draft.signal_id = requested_signal_id
       AND signal.scope_type = 'adelphi'
       AND signal.scope_id = pilot_scope_id
       AND signal.created_by_party_id = actor_party_id
       AND signal.status IN ('draft', 'rejected')
     FOR UPDATE OF signal;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demand draft is unavailable or no longer editable'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.operating_demand_signal
       SET status = 'superseded'
     WHERE id = old_signal.id AND status = old_signal.status;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demand draft changed before revision'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_demand_signal (
        scope_type, scope_id, work_type, period_start, period_end,
        required_hours, priority, source, description, status, created_by_party_id
    ) VALUES (
        'adelphi', pilot_scope_id, requested_work_type,
        requested_period_start, requested_period_end, requested_required_hours,
        requested_priority, 'planning', NULLIF(pg_catalog.btrim(requested_description), ''),
        'draft', actor_party_id
    ) RETURNING id INTO replacement_signal_id;

    -- Keep the existing receipt-backed own-history projection compatible.
    INSERT INTO public.operating_demand_draft_receipt (
        operator_id, request_id, location_id, signal_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        replacement_signal_id, input_digest
    );

    INSERT INTO public.operating_demand_draft_revision_receipt (
        operator_id, request_id, location_id, original_signal_id,
        replacement_signal_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        old_signal.id, replacement_signal_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'signal_id', replacement_signal_id,
        'replaced_signal_id', old_signal.id,
        'status', 'draft',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.revise_location_operating_pilot_demand_draft(
    UUID, UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.revise_location_operating_pilot_demand_draft(
    UUID, UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.revise_location_operating_pilot_demand_draft(
    UUID, UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT
) TO kokonut_runtime;

COMMENT ON FUNCTION kokonut_security.revise_location_operating_pilot_demand_draft(
    UUID, UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT
) IS
'Revises only the authenticated operator own receipt-backed planning demand draft or rejected record at the exact granted location; it retains the old version as superseded and creates a private draft without submitting or reviewing it.';
COMMENT ON TABLE public.operating_demand_draft_revision_receipt IS
'Private idempotency and revision-link receipt for operator edits to own demand drafts; excludes demand text and values.';

COMMIT;
