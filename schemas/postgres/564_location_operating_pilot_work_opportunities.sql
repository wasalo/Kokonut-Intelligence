-- Expose bounded location work opportunities and create private self-claims.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_work_claim_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    work_item_id UUID NOT NULL REFERENCES public.work_item(id) ON DELETE RESTRICT,
    claim_id UUID NOT NULL UNIQUE REFERENCES public.work_item_claim(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_work_claim_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.operating_work_claim_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;

GRANT SELECT (operator_id, request_id, location_id, work_item_id, claim_id, input_digest)
    ON TABLE public.operating_work_claim_receipt TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, request_id, location_id, work_item_id, claim_id, input_digest)
    ON TABLE public.operating_work_claim_receipt TO kokonut_operating_pilot_reader;

GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_operating_pilot_reader;
GRANT SELECT (scope_type, scope_id, status) ON TABLE public.operating_pilot_scope
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, location_id, status) ON TABLE public.farm
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_operating_pilot_reader;
GRANT SELECT (
    id, organization_id, location_id, title, work_type, priority, status,
    selection_mode, estimated_effort_hours, allocation_status, due_at
) ON TABLE public.work_item TO kokonut_operating_pilot_reader;
GRANT UPDATE (id) ON TABLE public.operator_identity, public.party,
    public.operator_governance_party_binding, public.operating_pilot_scope,
    public.farm
    TO kokonut_operating_pilot_reader;
GRANT UPDATE (allocation_status) ON TABLE public.work_item
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, work_item_id, claimant_party_id, status)
    ON TABLE public.work_item_claim TO kokonut_operating_pilot_reader;
GRANT INSERT (work_item_id, claimant_party_id, proposed_effort_hours)
    ON TABLE public.work_item_claim TO kokonut_operating_pilot_reader;
GRANT INSERT (work_item_id, claim_id, actor_party_id, event_type, note)
    ON TABLE public.work_item_selection_event TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_operating_pilot_reader;

DO $$
DECLARE column_name TEXT;
        role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.work_item_claim, public.work_item_selection_event, public.operating_work_claim_receipt FROM %I',
                role_name
            );
            EXECUTE format(
                'REVOKE UPDATE (allocation_status) ON TABLE public.work_item FROM %I',
                role_name
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.work_item_claim'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I) ON TABLE public.work_item_claim FROM %2$I',
                    column_name, role_name
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_work_opportunities(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    party_ids UUID[] := ARRAY[]::UUID[];
    binding_record RECORD;
    v_claimant_party_id UUID;
    pilot_scope_id UUID;
    opportunities JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR requested_location_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Work opportunities require signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'claim_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Work opportunities require an exact location claim-own grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Work opportunity page is outside its bounds'
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
        party_ids := pg_catalog.array_append(party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(party_ids) <> 1 THEN
        RAISE EXCEPTION 'Work opportunity access requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    v_claimant_party_id := party_ids[1];

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

    WITH page_rows AS (
        SELECT item.id, item.title, item.work_type, item.priority::TEXT AS priority,
               item.status::TEXT AS status, item.selection_mode,
               item.estimated_effort_hours, item.due_at, item.allocation_status,
               (claim.id IS NOT NULL) AS has_own_claim,
               claim.status AS own_claim_status
          FROM public.work_item AS item
          JOIN public.location AS location
            ON location.id = item.location_id
           AND location.organization_id = item.organization_id
          LEFT JOIN public.work_item_claim AS claim
            ON claim.work_item_id = item.id
           AND claim.claimant_party_id = v_claimant_party_id
         WHERE item.location_id = requested_location_id
           AND item.organization_id = location.organization_id
           AND item.selection_mode <> 'assigned'
           AND item.allocation_status IN ('open', 'claimed')
           AND item.status NOT IN ('done', 'cancelled')
           AND EXISTS (
               SELECT 1 FROM public.operating_pilot_scope AS active_scope
                WHERE active_scope.scope_type = 'adelphi'
                  AND active_scope.scope_id = pilot_scope_id
                  AND active_scope.status = 'active'
           )
         ORDER BY CASE item.priority::TEXT
                      WHEN 'critical' THEN 4 WHEN 'high' THEN 3
                      WHEN 'medium' THEN 2 ELSE 1 END DESC,
                  item.due_at NULLS LAST, item.id
         OFFSET requested_offset
         LIMIT requested_limit + 1
    ), numbered_page AS (
        SELECT pg_catalog.row_number() OVER (
                   ORDER BY CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3
                             WHEN 'medium' THEN 2 ELSE 1 END DESC,
                            due_at NULLS LAST, id
               )::INTEGER AS page_sequence,
               *
          FROM page_rows
    )
    SELECT pg_catalog.jsonb_build_object(
        'scope_configured', TRUE,
        'limit', requested_limit,
        'offset', requested_offset,
        'items', COALESCE(
            pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_object(
                    'work_item_id', page.id,
                    'title', page.title,
                    'work_type', page.work_type,
                    'priority', page.priority,
                    'status', page.status,
                    'selection_mode', page.selection_mode,
                    'estimated_effort_hours', page.estimated_effort_hours,
                    'due_at', page.due_at,
                    'allocation_status', page.allocation_status,
                    'has_own_claim', page.has_own_claim,
                    'own_claim_status', page.own_claim_status
                ) ORDER BY page.page_sequence
            ) FILTER (WHERE page.page_sequence <= requested_limit),
            '[]'::JSONB
        ),
        'has_more', COALESCE(pg_catalog.bool_or(page.page_sequence > requested_limit), FALSE),
        'next_offset', CASE
            WHEN COALESCE(pg_catalog.bool_or(page.page_sequence > requested_limit), FALSE)
                THEN requested_offset + requested_limit
            ELSE NULL
        END
    ) INTO opportunities
      FROM numbered_page AS page;

    RETURN opportunities;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.claim_location_operating_pilot_work(
    requested_location_id UUID,
    requested_work_item_id UUID,
    requested_request_id UUID,
    requested_effort_hours NUMERIC
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    party_ids UUID[] := ARRAY[]::UUID[];
    binding_record RECORD;
    v_claimant_party_id UUID;
    pilot_scope_id UUID;
    input_digest BYTEA;
    existing_receipt RECORD;
    existing_claim RECORD;
    item_record RECORD;
    created_claim_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_work_item_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Work claim requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'claim_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Work claim requires an exact location claim-own grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_effort_hours IS NOT NULL
       AND (requested_effort_hours < 0 OR requested_effort_hours > 100000
            OR pg_catalog.scale(requested_effort_hours) > 2) THEN
        RAISE EXCEPTION 'Proposed effort is invalid or outside its bounds'
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
        party_ids := pg_catalog.array_append(party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(party_ids) <> 1 THEN
        RAISE EXCEPTION 'Work claim requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    v_claimant_party_id := party_ids[1];

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
            'work_item_id', requested_work_item_id,
            'proposed_effort_hours', requested_effort_hours
        )::TEXT,
        'UTF8'
    ));
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.work_item_id, receipt.claim_id, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_work_claim_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.work_item_id IS DISTINCT FROM requested_work_item_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Work claim request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT claim.status INTO existing_claim
          FROM public.work_item_claim AS claim
         WHERE claim.id = existing_receipt.claim_id;
        IF existing_claim.status IS NULL THEN
            RAISE EXCEPTION 'Work claim receipt lost its claim';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'work_item_id', requested_work_item_id,
            'claim_id', existing_receipt.claim_id,
            'status', existing_claim.status,
            'replayed', TRUE
        );
    END IF;

    SELECT item.id, item.status::TEXT AS status, item.selection_mode,
           item.allocation_status, item.organization_id
      INTO item_record
      FROM public.work_item AS item
      JOIN public.location AS location
        ON location.id = item.location_id
       AND location.organization_id = item.organization_id
      JOIN public.operating_pilot_scope AS scope
        ON scope.scope_type = 'adelphi'
       AND scope.scope_id = pilot_scope_id
       AND scope.status = 'active'
      JOIN public.farm AS pilot_farm
        ON pilot_farm.id = scope.scope_id
       AND pilot_farm.location_id = item.location_id
       AND pilot_farm.status = 'active'
     WHERE item.id = requested_work_item_id
       AND item.location_id = requested_location_id
     FOR UPDATE OF item;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Work opportunity is unavailable at this location'
            USING ERRCODE = '42501';
    END IF;
    IF item_record.selection_mode = 'assigned'
       OR item_record.allocation_status NOT IN ('open', 'claimed')
       OR item_record.status IN ('done', 'cancelled') THEN
        RAISE EXCEPTION 'Work opportunity is not open for claims'
            USING ERRCODE = '42501';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.work_item_claim AS prior_claim
         WHERE prior_claim.work_item_id = requested_work_item_id
           AND prior_claim.claimant_party_id = v_claimant_party_id
    ) THEN
        RAISE EXCEPTION 'This person already has a claim for the work opportunity'
            USING ERRCODE = '23505';
    END IF;

    INSERT INTO public.work_item_claim (
        work_item_id, claimant_party_id, proposed_effort_hours
    ) VALUES (
        requested_work_item_id, v_claimant_party_id, requested_effort_hours
    ) RETURNING id INTO created_claim_id;
    UPDATE public.work_item
       SET allocation_status = 'claimed'
     WHERE id = requested_work_item_id;
    INSERT INTO public.work_item_selection_event (
        work_item_id, claim_id, actor_party_id, event_type, note
    ) VALUES (
        requested_work_item_id, created_claim_id, v_claimant_party_id,
        'claimed', 'Party proposed a self-claim through the operating-pilot Gateway'
    );
    INSERT INTO public.operating_work_claim_receipt (
        operator_id, request_id, location_id, work_item_id, claim_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_work_item_id, created_claim_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'work_item_id', requested_work_item_id,
        'claim_id', created_claim_id,
        'status', 'proposed',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_work_opportunities(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_operating_pilot_reader;
ALTER FUNCTION kokonut_security.claim_location_operating_pilot_work(UUID, UUID, UUID, NUMERIC)
    OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_work_opportunities(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.claim_location_operating_pilot_work(UUID, UUID, UUID, NUMERIC)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_work_opportunities(UUID, INTEGER, INTEGER)
    TO kokonut_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.claim_location_operating_pilot_work(UUID, UUID, UUID, NUMERIC)
    TO kokonut_runtime;

COMMENT ON TABLE public.operating_work_claim_receipt IS
'Private append-only idempotency receipt for Gateway work-opportunity self-claims.';
COMMENT ON FUNCTION kokonut_security.location_operating_pilot_work_opportunities(UUID, INTEGER, INTEGER) IS
'Returns bounded, location-scoped non-assigned work opportunities with only the authenticated operator party own-claim state.';
COMMENT ON FUNCTION kokonut_security.claim_location_operating_pilot_work(UUID, UUID, UUID, NUMERIC) IS
'Creates an idempotent self-claim proposal for an open location opportunity; independent allocation/review and work execution remain separate.';

COMMIT;
