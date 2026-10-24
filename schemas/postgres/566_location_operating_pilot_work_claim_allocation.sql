-- Add a separate, explicit allocation action for independently accepted claims.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_work_claim_allocation_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    work_item_id UUID NOT NULL REFERENCES public.work_item(id) ON DELETE RESTRICT,
    claim_id UUID NOT NULL UNIQUE REFERENCES public.work_item_claim(id) ON DELETE RESTRICT,
    assigned_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_work_claim_allocation_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.operating_work_claim_allocation_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT (
    operator_id, request_id, location_id, work_item_id, claim_id,
    assigned_party_id, input_digest
) ON TABLE public.operating_work_claim_allocation_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (
    operator_id, request_id, location_id, work_item_id, claim_id,
    assigned_party_id, input_digest
) ON TABLE public.operating_work_claim_allocation_receipt
    TO kokonut_operating_pilot_reader;

GRANT SELECT (id, location_id, organization_id, title, work_type, priority,
              status, selection_mode, estimated_effort_hours, due_at,
              allocation_status, assignee_party_id)
    ON TABLE public.work_item TO kokonut_operating_pilot_reader;
GRANT UPDATE (allocation_status, assignee_party_id)
    ON TABLE public.work_item TO kokonut_operating_pilot_reader;
GRANT SELECT (id, work_item_id, claimant_party_id, proposed_effort_hours,
              status, reviewed_at, created_at)
    ON TABLE public.work_item_claim TO kokonut_operating_pilot_reader;
GRANT SELECT (id, display_name, party_type, status)
    ON TABLE public.party TO kokonut_operating_pilot_reader;

DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_work_claim_allocation_receipt FROM %I',
                role_name
            );
            EXECUTE format(
                'REVOKE UPDATE (allocation_status, assignee_party_id) ON TABLE public.work_item FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_work_claim_allocation_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    party_ids UUID[] := ARRAY[]::UUID[];
    binding_record RECORD;
    allocator_party_id UUID;
    pilot_scope_id UUID;
    allocation_page JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR requested_location_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Work-claim allocation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'allocate', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Work-claim allocation requires an exact location allocation grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Work-claim allocation page is outside its bounds'
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
    LOOP
        party_ids := pg_catalog.array_append(party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(party_ids) <> 1 THEN
        RAISE EXCEPTION 'Work-claim allocation requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    allocator_party_id := party_ids[1];

    SELECT scope.scope_id
      INTO pilot_scope_id
      FROM public.operating_pilot_scope AS scope
      JOIN public.farm AS pilot_farm
        ON pilot_farm.id = scope.scope_id
       AND pilot_farm.location_id = requested_location_id
       AND pilot_farm.status = 'active'
     WHERE scope.scope_type = 'adelphi'
       AND scope.status = 'active';
    IF pilot_scope_id IS NULL THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    WITH eligible AS (
        SELECT claim.id, claim.work_item_id, claim.claimant_party_id,
               claimant.display_name AS claimant_name,
               item.title, item.work_type, item.priority::TEXT AS priority,
               item.estimated_effort_hours, item.due_at, claim.proposed_effort_hours,
               claim.reviewed_at, claim.created_at
          FROM public.work_item_claim AS claim
          JOIN public.work_item AS item ON item.id = claim.work_item_id
          JOIN public.location AS location
            ON location.id = item.location_id
           AND location.organization_id = item.organization_id
          JOIN public.party AS claimant
            ON claimant.id = claim.claimant_party_id
           AND claimant.party_type = 'person'
           AND claimant.status = 'active'
         WHERE item.location_id = requested_location_id
           AND item.organization_id = location.organization_id
           AND item.selection_mode <> 'assigned'
           AND item.allocation_status = 'claimed'
           AND item.assignee_party_id IS NULL
           AND item.status NOT IN ('done', 'cancelled')
           AND claim.status = 'accepted'
           AND claim.claimant_party_id <> allocator_party_id
           AND NOT EXISTS (
               SELECT 1
                 FROM public.work_item_claim AS competing
                WHERE competing.work_item_id = item.id
                  AND competing.status IN ('proposed', 'accepted')
                  AND competing.id <> claim.id
           )
           AND EXISTS (
               SELECT 1 FROM public.operating_pilot_scope AS active_scope
                WHERE active_scope.scope_type = 'adelphi'
                  AND active_scope.scope_id = pilot_scope_id
                  AND active_scope.status = 'active'
           )
         ORDER BY CASE item.priority::TEXT
                      WHEN 'critical' THEN 4 WHEN 'high' THEN 3
                      WHEN 'medium' THEN 2 ELSE 1 END DESC,
                  item.due_at NULLS LAST, claim.reviewed_at, claim.id
         OFFSET requested_offset
         LIMIT requested_limit + 1
    ), numbered_page AS (
        SELECT pg_catalog.row_number() OVER (
                   ORDER BY CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3
                             WHEN 'medium' THEN 2 ELSE 1 END DESC,
                            due_at NULLS LAST, reviewed_at, id
               )::INTEGER AS page_sequence,
               *
          FROM eligible
    )
    SELECT pg_catalog.jsonb_build_object(
        'scope_configured', TRUE,
        'limit', requested_limit,
        'offset', requested_offset,
        'items', COALESCE(
            pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_object(
                    'claim_id', page.id,
                    'work_item_id', page.work_item_id,
                    'claimant_name', page.claimant_name,
                    'title', page.title,
                    'work_type', page.work_type,
                    'priority', page.priority,
                    'estimated_effort_hours', page.estimated_effort_hours,
                    'proposed_effort_hours', page.proposed_effort_hours,
                    'due_at', page.due_at,
                    'accepted_at', page.reviewed_at
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
    ) INTO allocation_page
      FROM numbered_page AS page;

    RETURN allocation_page;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.allocate_location_operating_pilot_work_claim(
    requested_location_id UUID,
    requested_claim_id UUID,
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
    party_ids UUID[] := ARRAY[]::UUID[];
    binding_record RECORD;
    allocator_party_id UUID;
    pilot_scope_id UUID;
    input_digest BYTEA;
    existing_receipt RECORD;
    claim_record RECORD;
    active_claim_count INTEGER;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_claim_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Work-claim allocation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'allocate', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Work-claim allocation requires an exact location allocation grant'
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
        party_ids := pg_catalog.array_append(party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(party_ids) <> 1 THEN
        RAISE EXCEPTION 'Work-claim allocation requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    allocator_party_id := party_ids[1];

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
        pg_catalog.jsonb_build_object('claim_id', requested_claim_id)::TEXT,
        'UTF8'
    ));
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.work_item_id, receipt.claim_id,
           receipt.assigned_party_id, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_work_claim_allocation_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.claim_id IS DISTINCT FROM requested_claim_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Work-claim allocation request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'claim_id', requested_claim_id,
            'work_item_id', existing_receipt.work_item_id,
            'allocation_status', 'allocated',
            'replayed', TRUE
        );
    END IF;

    SELECT claim.id, claim.work_item_id, claim.claimant_party_id,
           item.allocation_status, item.selection_mode,
           item.status::TEXT AS work_status, item.assignee_party_id
      INTO claim_record
      FROM public.work_item_claim AS claim
      JOIN public.work_item AS item ON item.id = claim.work_item_id
      JOIN public.location AS location
        ON location.id = item.location_id
       AND location.organization_id = item.organization_id
      JOIN public.party AS claimant
        ON claimant.id = claim.claimant_party_id
       AND claimant.party_type = 'person'
       AND claimant.status = 'active'
     WHERE claim.id = requested_claim_id
       AND item.location_id = requested_location_id
     FOR UPDATE OF claim, item;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Accepted work claim is unavailable at this location'
            USING ERRCODE = '42501';
    END IF;
    IF claim_record.claimant_party_id = allocator_party_id THEN
        RAISE EXCEPTION 'A claimant cannot allocate their own work claim'
            USING ERRCODE = '42501';
    END IF;
    IF claim_record.allocation_status <> 'claimed'
       OR claim_record.assignee_party_id IS NOT NULL
       OR claim_record.selection_mode = 'assigned'
       OR claim_record.work_status IN ('done', 'cancelled')
       OR NOT EXISTS (
           SELECT 1 FROM public.operating_pilot_scope AS active_scope
            WHERE active_scope.scope_type = 'adelphi'
              AND active_scope.scope_id = pilot_scope_id
              AND active_scope.status = 'active'
       ) THEN
        RAISE EXCEPTION 'Work opportunity is no longer eligible for allocation'
            USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.work_item_claim AS selected
         WHERE selected.id = requested_claim_id
           AND selected.work_item_id = claim_record.work_item_id
           AND selected.status = 'accepted'
    ) THEN
        RAISE EXCEPTION 'Only an independently accepted claim can be allocated'
            USING ERRCODE = '42501';
    END IF;
    SELECT pg_catalog.count(*)::INTEGER
      INTO active_claim_count
      FROM public.work_item_claim AS competing
     WHERE competing.work_item_id = claim_record.work_item_id
       AND competing.status IN ('proposed', 'accepted');
    IF active_claim_count <> 1 THEN
        RAISE EXCEPTION 'Resolve all competing proposed or accepted claims before allocation'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.work_item
       SET allocation_status = 'allocated',
           assignee_party_id = claim_record.claimant_party_id
     WHERE id = claim_record.work_item_id;
    INSERT INTO public.work_item_selection_event (
        work_item_id, claim_id, actor_party_id, event_type, note
    ) VALUES (
        claim_record.work_item_id, requested_claim_id, allocator_party_id,
        'allocated', 'Independently accepted work claim allocated by location operator'
    );
    INSERT INTO public.operating_work_claim_allocation_receipt (
        operator_id, request_id, location_id, work_item_id, claim_id,
        assigned_party_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        claim_record.work_item_id, requested_claim_id,
        claim_record.claimant_party_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'claim_id', requested_claim_id,
        'work_item_id', claim_record.work_item_id,
        'allocation_status', 'allocated',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_work_claim_allocation_queue(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_operating_pilot_reader;
ALTER FUNCTION kokonut_security.allocate_location_operating_pilot_work_claim(UUID, UUID, UUID)
    OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_work_claim_allocation_queue(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.allocate_location_operating_pilot_work_claim(UUID, UUID, UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_work_claim_allocation_queue(UUID, INTEGER, INTEGER)
    TO kokonut_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.allocate_location_operating_pilot_work_claim(UUID, UUID, UUID)
    TO kokonut_runtime;

COMMENT ON TABLE public.operating_work_claim_allocation_receipt IS
'Private append-only idempotency receipt for explicit location-scoped work-claim allocation.';
COMMENT ON FUNCTION kokonut_security.location_operating_pilot_work_claim_allocation_queue(UUID, INTEGER, INTEGER) IS
'Returns bounded accepted claims eligible for allocation; claimant names are visible only under the exact allocate scope.';
COMMENT ON FUNCTION kokonut_security.allocate_location_operating_pilot_work_claim(UUID, UUID, UUID) IS
'Allocates exactly one independently accepted, non-self claim after all competing claims are resolved; assignment remains separate from work lifecycle state.';

COMMIT;
