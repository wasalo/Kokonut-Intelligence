-- Create an attributed, location-bound demand draft through the signed Gateway.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_demand_draft_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    signal_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_demand_signal(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_demand_draft_receipt FROM PUBLIC;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_operating_pilot_reader;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party, public.operating_pilot_scope,
    public.farm TO kokonut_operating_pilot_reader;
GRANT SELECT (id, status) ON TABLE public.operating_demand_signal
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, signal_id, input_digest)
    ON TABLE public.operating_demand_draft_receipt TO kokonut_operating_pilot_reader;
GRANT INSERT (scope_type, scope_id, work_type, period_start, period_end,
              required_hours, priority, source, description, status, created_by_party_id)
    ON TABLE public.operating_demand_signal TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, request_id, location_id, signal_id, input_digest)
    ON TABLE public.operating_demand_draft_receipt TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_operating_pilot_reader;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_operating_pilot_demand_draft(
    requested_location_id UUID,
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
    actor_party_id UUID;
    pilot_scope_id UUID;
    input_digest BYTEA;
    existing_receipt public.operating_demand_draft_receipt%ROWTYPE;
    existing_status TEXT;
    demand_signal_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Demand draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Demand draft requires an active exact location create grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_work_type IS NULL
       OR requested_work_type <> btrim(requested_work_type)
       OR char_length(requested_work_type) NOT BETWEEN 1 AND 50
       OR requested_work_type !~ '^[[:alnum:]][[:alnum:] _./-]*$'
       OR requested_period_start IS NULL
       OR requested_period_end IS NULL
       OR requested_period_end < requested_period_start
       OR requested_period_end > requested_period_start + 366
       OR requested_required_hours IS NULL
       OR requested_required_hours <= 0
       OR requested_required_hours > 100000
       OR scale(requested_required_hours) > 2
       OR requested_priority IS NULL
       OR requested_priority NOT IN ('low', 'medium', 'high', 'critical')
       OR requested_description IS NOT NULL
          AND char_length(requested_description) > 2000 THEN
        RAISE EXCEPTION 'Demand draft input is invalid or outside its bounds'
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
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Operator has no active human governance-party binding'
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
     FOR KEY SHARE OF scope, pilot_farm;
    IF pilot_scope_id IS NULL THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    input_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'work_type', requested_work_type,
            'period_start', requested_period_start,
            'period_end', requested_period_end,
            'required_hours', requested_required_hours,
            'priority', requested_priority,
            'description', NULLIF(btrim(requested_description), '')
        )::TEXT,
        'UTF8'
    ));

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.operator_id, receipt.request_id, receipt.location_id,
           receipt.signal_id, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_demand_draft_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Demand draft request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT signal.status INTO existing_status
          FROM public.operating_demand_signal AS signal
         WHERE signal.id = existing_receipt.signal_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Demand draft receipt lost its signal';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'signal_id', existing_receipt.signal_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    INSERT INTO public.operating_demand_signal (
        scope_type, scope_id, work_type, period_start, period_end,
        required_hours, priority, source, description, status, created_by_party_id
    ) VALUES (
        'adelphi', pilot_scope_id, requested_work_type,
        requested_period_start, requested_period_end, requested_required_hours,
        requested_priority, 'planning', NULLIF(btrim(requested_description), ''),
        'draft', actor_party_id
    ) RETURNING id INTO demand_signal_id;

    INSERT INTO public.operating_demand_draft_receipt (
        operator_id, request_id, location_id, signal_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        demand_signal_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'signal_id', demand_signal_id,
        'status', 'draft',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_operating_pilot_demand_draft(
    UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.create_location_operating_pilot_demand_draft(
    UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_location_operating_pilot_demand_draft(
    UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT
) TO kokonut_runtime;

DO $$
DECLARE role_name TEXT;
        column_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
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
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_demand_draft_receipt FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END;
$$;

COMMIT;
