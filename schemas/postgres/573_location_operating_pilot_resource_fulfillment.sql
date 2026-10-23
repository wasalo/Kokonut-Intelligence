-- Record a separate, human-confirmed fulfillment for approved Kernel resource requests.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_resource_request_fulfillment_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    resource_request_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_resource_request(id) ON DELETE RESTRICT,
    fulfiller_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_resource_request_fulfillment_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
REVOKE ALL ON TABLE public.operating_resource_request_fulfillment_receipt
    FROM kokonut_operating_pilot_reader;
GRANT SELECT (
    operator_id, request_id, location_id, resource_request_id,
    fulfiller_party_id, input_digest
)
ON TABLE public.operating_resource_request_fulfillment_receipt
TO kokonut_operating_pilot_reader;
GRANT INSERT (
    operator_id, request_id, location_id, resource_request_id,
    fulfiller_party_id, input_digest
)
ON TABLE public.operating_resource_request_fulfillment_receipt
TO kokonut_operating_pilot_reader;

GRANT UPDATE (decision, status, updated_at)
ON TABLE public.operating_resource_request
TO kokonut_operating_pilot_reader;
GRANT SELECT (id, operator_id, location_id, status, submitted_request_id)
ON TABLE public.operating_resource_request_draft
TO kokonut_operating_pilot_reader;

DO $$
DECLARE
    role_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_resource_request_fulfillment_receipt FROM %I',
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

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_resource_fulfillment_queue(
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
    active_party_ids UUID[] := ARRAY[]::UUID[];
    fulfiller_party_id UUID;
    pilot_scope_id UUID;
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR requested_location_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Resource fulfillment queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'fulfill', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Resource fulfillment queue requires an exact location fulfillment grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Resource fulfillment page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT pg_catalog.array_agg(binding.party_id ORDER BY binding.party_id)
      INTO active_party_ids
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF coalesce(pg_catalog.cardinality(active_party_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Resource fulfillment requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    fulfiller_party_id := active_party_ids[1];

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

    WITH eligible AS MATERIALIZED (
        SELECT request.id, request.resource_type, request.description,
               request.urgency, request.requested_by
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
          JOIN public.operating_resource_request_review_decision AS approval
            ON approval.resource_request_id = request.id
           AND approval.location_id = requested_location_id
           AND approval.decision = 'approved'
         WHERE request.scope_type = 'adelphi'
           AND request.scope_id = pilot_scope_id
           AND request.status = 'reviewed'
           AND request.decision = 'approved'
           AND request.requested_by_party_id <> fulfiller_party_id
           AND NOT EXISTS (
               SELECT 1
                 FROM public.operating_resource_request_fulfillment_receipt AS receipt
                WHERE receipt.resource_request_id = request.id
           )
    ), selected AS (
        SELECT *
          FROM eligible
         ORDER BY requested_by DESC, id DESC
         LIMIT requested_limit + 1 OFFSET requested_offset
    ), numbered AS (
        SELECT selected.*,
               pg_catalog.row_number() OVER (
                   ORDER BY selected.requested_by DESC, selected.id DESC
               ) AS page_row
          FROM selected
    ), page AS (
        SELECT coalesce(
                   pg_catalog.jsonb_agg(
                       pg_catalog.jsonb_build_object(
                           'resource_request_id', numbered.id,
                           'resource_type', numbered.resource_type,
                           'description', numbered.description,
                           'urgency', numbered.urgency,
                           'requested_by', numbered.requested_by
                       ) ORDER BY numbered.page_row
                   ) FILTER (WHERE numbered.page_row <= requested_limit),
                   '[]'::JSONB
               ) AS items,
               pg_catalog.bool_or(numbered.page_row > requested_limit) AS has_more
          FROM numbered
    )
    SELECT pg_catalog.jsonb_build_object(
               'limit', requested_limit,
               'offset', requested_offset,
               'items', page.items,
               'has_more', coalesce(page.has_more, FALSE),
               'next_offset', CASE
                   WHEN coalesce(page.has_more, FALSE)
                       THEN requested_offset + requested_limit
                   ELSE NULL
               END,
               'total', (SELECT pg_catalog.count(*) FROM eligible)
           )
      INTO result
      FROM page;
    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_resource_fulfillment_queue(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_resource_fulfillment_queue(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_resource_fulfillment_queue(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_resource_fulfillment_queue(
    UUID, INTEGER, INTEGER
) FROM kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.fulfill_location_operating_pilot_resource_request(
    requested_location_id UUID,
    requested_resource_request_id UUID,
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
    fulfiller_party_id UUID;
    pilot_scope_id UUID;
    input_digest BYTEA;
    existing_receipt RECORD;
    request_record RECORD;
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
        RAISE EXCEPTION 'Resource fulfillment requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'fulfill', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Resource fulfillment requires an exact location fulfillment grant'
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
    IF coalesce(pg_catalog.cardinality(active_party_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Resource fulfillment requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    fulfiller_party_id := active_party_ids[1];

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
            'resource_request_id', requested_resource_request_id,
            'decision', 'fulfilled'
        )::TEXT,
        'UTF8'
    ));
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.location_id, receipt.resource_request_id, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_resource_request_fulfillment_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.resource_request_id IS DISTINCT FROM requested_resource_request_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Resource fulfillment request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        IF NOT EXISTS (
            SELECT 1
              FROM public.operating_resource_request AS request
              JOIN public.operating_resource_request_draft_submission_receipt AS submission
                ON submission.resource_request_id = request.id
               AND submission.location_id = requested_location_id
              JOIN public.operating_resource_request_review_decision AS approval
                ON approval.resource_request_id = request.id
               AND approval.location_id = requested_location_id
               AND approval.decision = 'approved'
             WHERE request.id = requested_resource_request_id
               AND request.scope_type = 'adelphi'
               AND request.scope_id = pilot_scope_id
               AND request.status = 'closed'
               AND request.decision = 'fulfilled'
        ) THEN
            RAISE EXCEPTION 'Fulfillment receipt does not match the completed resource request'
                USING ERRCODE = '40001';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'resource_request_id', requested_resource_request_id,
            'status', 'closed',
            'decision', 'fulfilled',
            'replayed', TRUE
        );
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.operating_resource_request_draft_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) OR EXISTS (
        SELECT 1 FROM public.operating_resource_request_draft_revision_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) OR EXISTS (
        SELECT 1 FROM public.operating_resource_request_draft_submission_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) OR EXISTS (
        SELECT 1 FROM public.operating_resource_request_review_decision AS receipt
         WHERE receipt.reviewer_operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) THEN
        RAISE EXCEPTION 'Resource fulfillment request ID conflicts with another resource operation'
            USING ERRCODE = '23505';
    END IF;

    SELECT request.id, request.requested_by_party_id,
           request.scope_id, request.status, request.decision
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
      JOIN public.operating_resource_request_review_decision AS approval
        ON approval.resource_request_id = request.id
       AND approval.location_id = requested_location_id
       AND approval.decision = 'approved'
     WHERE request.id = requested_resource_request_id
       AND request.scope_type = 'adelphi'
       AND request.scope_id = pilot_scope_id
     FOR UPDATE OF request, draft;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Approved Kernel resource request is unavailable for fulfillment'
            USING ERRCODE = '42501';
    END IF;
    IF request_record.requested_by_party_id = fulfiller_party_id THEN
        RAISE EXCEPTION 'Resource requesters cannot confirm their own fulfillment'
            USING ERRCODE = '42501';
    END IF;
    IF request_record.status <> 'reviewed' OR request_record.decision <> 'approved' THEN
        RAISE EXCEPTION 'Only approved and reviewed Kernel requests can be fulfilled'
            USING ERRCODE = '23505';
    END IF;

    UPDATE public.operating_resource_request
       SET status = 'closed',
           decision = 'fulfilled',
           updated_at = pg_catalog.clock_timestamp()
     WHERE id = requested_resource_request_id
       AND scope_id = pilot_scope_id
       AND status = 'reviewed'
       AND decision = 'approved';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Resource request changed before fulfillment was recorded'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_resource_request_fulfillment_receipt (
        operator_id, request_id, location_id, resource_request_id,
        fulfiller_party_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_resource_request_id, fulfiller_party_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'resource_request_id', requested_resource_request_id,
        'status', 'closed',
        'decision', 'fulfilled',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.fulfill_location_operating_pilot_resource_request(
    UUID, UUID, UUID
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.fulfill_location_operating_pilot_resource_request(
    UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.fulfill_location_operating_pilot_resource_request(
    UUID, UUID, UUID
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.fulfill_location_operating_pilot_resource_request(
    UUID, UUID, UUID
) FROM kokonut_directus_runtime;

COMMENT ON TABLE public.operating_resource_request_fulfillment_receipt IS
'Private append-only human confirmation and idempotency receipt for completed, independently approved Kernel resource requests. It does not represent inventory, expense, or payment evidence.';
COMMENT ON FUNCTION kokonut_security.location_operating_pilot_resource_fulfillment_queue(
    UUID, INTEGER, INTEGER
) IS
'Returns a bounded exact-location queue of approved, receipt-backed Kernel requests awaiting fulfillment confirmation; requester identity and approval reasons are omitted.';
COMMENT ON FUNCTION kokonut_security.fulfill_location_operating_pilot_resource_request(
    UUID, UUID, UUID
) IS
'Records one exact-location human confirmation that an independently approved, receipt-backed Kernel resource request was completed; it records no inventory, expense, or payment.';

COMMIT;
