-- Allow a location to prepare an adoption program before the adoption-ready gate.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_solution_adoption_program(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_request_id UUID,
    requested_adoption_pathway TEXT,
    requested_local_adaptation_policy TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    program_id UUID,
    solution_id UUID,
    program_status TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    solution_record RECORD;
    prior_receipt RECORD;
    payload_digest BYTEA;
    created_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Adoption program creation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_solution_id IS NULL
       OR requested_request_id IS NULL
       OR requested_adoption_pathway IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_adoption_pathway)) NOT BETWEEN 1 AND 2000
       OR pg_catalog.octet_length(pg_catalog.convert_to(requested_adoption_pathway, 'UTF8')) > 4000
       OR requested_local_adaptation_policy IS NOT NULL
          AND (pg_catalog.length(requested_local_adaptation_policy) > 4000
               OR pg_catalog.octet_length(pg_catalog.convert_to(requested_local_adaptation_policy, 'UTF8')) > 8000)
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Adoption program draft input is invalid'
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
        RAISE EXCEPTION 'Adoption program creation requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    SELECT solution.id, solution.current_stage, solution.status
      INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.current_stage IN ('pilot_active', 'adoption_ready', 'adopting')
       AND solution.status = 'active'
     FOR UPDATE;
    IF solution_record.id IS NULL THEN
        RAISE EXCEPTION 'Adoption program requires an active eligible solution at this location'
            USING ERRCODE = '55000';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'solution_id', requested_solution_id,
                'adoption_pathway', pg_catalog.btrim(requested_adoption_pathway),
                'local_adaptation_policy', NULLIF(pg_catalog.btrim(requested_local_adaptation_policy), ''),
                'target_scope_type', 'location',
                'target_scope_id', requested_location_id,
                'target_population', '{}'::JSONB,
                'acknowledged', requested_acknowledged
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.actor_party_id, receipt.location_id, receipt.solution_id,
           receipt.program_id, receipt.payload_digest, receipt.created_at
      INTO prior_receipt
      FROM public.solution_adoption_program_creation_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.solution_id IS DISTINCT FROM requested_solution_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Adoption program request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.program_id, prior_receipt.solution_id,
                            'draft'::TEXT, prior_receipt.created_at, TRUE;
        RETURN;
    END IF;

    INSERT INTO public.solution_adoption_program AS created_program (
        solution_id, target_scope_type, target_scope_id, target_population,
        adoption_pathway, local_adaptation_policy, status, created_by_party_id
    ) VALUES (
        requested_solution_id, 'location', requested_location_id, '{}'::JSONB,
        pg_catalog.btrim(requested_adoption_pathway),
        NULLIF(pg_catalog.btrim(requested_local_adaptation_policy), ''),
        'draft', actor_party_id
    ) RETURNING created_program.id, created_program.created_at
      INTO program_id, created_time;

    INSERT INTO public.solution_adoption_program_creation_receipt (
        operator_id, actor_party_id, location_id, solution_id, program_id,
        request_id, payload_digest, created_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        requested_solution_id, program_id, requested_request_id,
        payload_digest, created_time
    );

    RETURN QUERY SELECT program_id, requested_solution_id, 'draft'::TEXT,
                        created_time, FALSE;
END;
$$;

ALTER FUNCTION kokonut_security.create_location_solution_adoption_program(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) OWNER TO kokonut_solution_adoption_program_creator;
REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_adoption_program(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_solution_adoption_program(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_adoption_program(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_solution_adoption_program(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) IS 'Creates an exact-location, human-attributed adoption program draft for an active location-origin solution at pilot_active, adoption_ready, or adopting; the active human, location scope, empty population, and immutable retry receipt are server controlled. It does not assess readiness, approve configuration, collect events, or launch adoption.';

COMMIT;
