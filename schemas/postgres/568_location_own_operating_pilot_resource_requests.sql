-- Expose only receipt-backed resource-request drafts owned by the signed operator.

BEGIN;

CREATE INDEX IF NOT EXISTS idx_operating_resource_request_draft_owner_updated
    ON public.operating_resource_request_draft(operator_id, location_id, updated_at DESC, id DESC);

GRANT SELECT (
    id, operator_id, location_id, scope_type, scope_id, requested_by_party_id,
    resource_type, description, urgency, requested_by, status, created_at, updated_at
)
ON TABLE public.operating_resource_request_draft
TO kokonut_operating_pilot_reader;
CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_own_resource_requests(
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
    actor_party_ids UUID[];
    actor_party_id UUID;
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Own resource read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'read_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Own resource read requires an exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Own resource page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT array_agg(binding.party_id ORDER BY binding.party_id)
      INTO actor_party_ids
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF coalesce(cardinality(actor_party_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Own resource read requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    actor_party_id := actor_party_ids[1];

    IF NOT EXISTS (
        SELECT 1
          FROM public.operating_pilot_scope AS scope
          JOIN public.farm AS pilot_farm
            ON pilot_farm.id = scope.scope_id
           AND pilot_farm.location_id = requested_location_id
           AND pilot_farm.status = 'active'
         WHERE scope.scope_type = 'adelphi'
           AND scope.status = 'active'
    ) THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    WITH eligible AS MATERIALIZED (
        SELECT draft.id, draft.resource_type, draft.description, draft.urgency,
               draft.requested_by, draft.status, draft.created_at, draft.updated_at
          FROM public.operating_resource_request_draft AS draft
         WHERE draft.operator_id = context_record.actor_id
           AND draft.location_id = requested_location_id
           AND draft.scope_type = 'adelphi'
           AND draft.requested_by_party_id = actor_party_id
           AND EXISTS (
               SELECT 1
                 FROM public.operating_pilot_scope AS scope
                 JOIN public.farm AS pilot_farm
                   ON pilot_farm.id = scope.scope_id
                  AND pilot_farm.location_id = requested_location_id
                  AND pilot_farm.status = 'active'
                WHERE scope.scope_type = 'adelphi'
                  AND scope.status = 'active'
                  AND scope.scope_id = draft.scope_id
           )
           AND EXISTS (
               SELECT 1
                 FROM public.operating_resource_request_draft_receipt AS receipt
                WHERE receipt.operator_id = context_record.actor_id
                  AND receipt.location_id = requested_location_id
                  AND receipt.draft_id = draft.id
           )
    ), selected AS (
        SELECT *
          FROM eligible
         ORDER BY updated_at DESC, id DESC
         LIMIT requested_limit + 1 OFFSET requested_offset
    ), page AS (
        SELECT selected.*,
               row_number() OVER (ORDER BY selected.updated_at DESC, selected.id DESC) AS page_row
          FROM selected
    ), page_result AS (
        SELECT coalesce(
                   jsonb_agg(
                       jsonb_build_object(
                           'draft_id', page.id,
                           'resource_type', page.resource_type,
                           'description', page.description,
                           'urgency', page.urgency,
                           'requested_by', page.requested_by,
                           'status', page.status,
                           'created_at', page.created_at,
                           'updated_at', page.updated_at
                       ) ORDER BY page.page_row
                   ) FILTER (WHERE page.page_row <= requested_limit),
                   '[]'::jsonb
               ) AS items,
               count(*) > requested_limit AS has_more
          FROM page
    )
    SELECT jsonb_build_object(
               'items', page_result.items,
               'limit', requested_limit,
               'offset', requested_offset,
               'has_more', page_result.has_more,
               'next_offset', CASE
                   WHEN page_result.has_more THEN requested_offset + requested_limit
                   ELSE NULL
               END,
               'total', (SELECT count(*) FROM eligible)
           )
      INTO result
      FROM page_result;

    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_own_resource_requests(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_own_resource_requests(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_own_resource_requests(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_own_resource_requests(
    UUID, INTEGER, INTEGER
) FROM kokonut_directus_runtime;
REVOKE ALL ON TABLE public.operating_resource_request_draft,
    public.operating_resource_request_draft_receipt FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE SELECT (
    id, operator_id, location_id, scope_type, scope_id, requested_by_party_id,
    resource_type, description, urgency, requested_by, status, submitted_request_id,
    created_at, updated_at
)
ON TABLE public.operating_resource_request_draft FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE INSERT (
    operator_id, location_id, scope_type, scope_id, requested_by_party_id,
    resource_type, description, urgency, requested_by
)
ON TABLE public.operating_resource_request_draft FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE UPDATE (
    id, operator_id, location_id, scope_type, scope_id, requested_by_party_id,
    resource_type, description, urgency, requested_by, status, submitted_request_id,
    created_at, updated_at
)
ON TABLE public.operating_resource_request_draft FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE REFERENCES (
    id, operator_id, location_id, scope_type, scope_id, requested_by_party_id,
    resource_type, description, urgency, requested_by, status, submitted_request_id,
    created_at, updated_at
)
ON TABLE public.operating_resource_request_draft FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE SELECT (
    operator_id, request_id, location_id, draft_id, input_digest, created_at
)
ON TABLE public.operating_resource_request_draft_receipt FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE INSERT (
    operator_id, request_id, location_id, draft_id, input_digest
)
ON TABLE public.operating_resource_request_draft_receipt FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE UPDATE (
    operator_id, request_id, location_id, draft_id, input_digest, created_at
)
ON TABLE public.operating_resource_request_draft_receipt FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE REFERENCES (
    operator_id, request_id, location_id, draft_id, input_digest, created_at
)
ON TABLE public.operating_resource_request_draft_receipt FROM kokonut_runtime, kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_own_resource_requests(
    UUID, INTEGER, INTEGER
) IS
'Returns bounded receipt-backed private resource drafts belonging to the signed operator at the exact active Adelphi location; it exposes no other operator data or idempotency digests.';

COMMIT;
