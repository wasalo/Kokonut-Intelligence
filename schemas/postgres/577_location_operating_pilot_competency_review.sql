-- Add independent review for submitted, private competency assessments.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_pilot_competency_review_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reviewer_operator_id UUID NOT NULL
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL
        REFERENCES public.party(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    draft_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_pilot_competency_draft(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('verified', 'rejected')),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (reviewer_operator_id, request_id),
    CHECK (reason IS NULL OR char_length(reason) <= 2000),
    CHECK (
        decision <> 'rejected'
        OR NULLIF(
            btrim(reason, ' ' || chr(9) || chr(10) || chr(13)), ''
        ) IS NOT NULL
    )
);
REVOKE ALL ON TABLE public.operating_pilot_competency_review_decision FROM PUBLIC;
REVOKE ALL ON TABLE public.operating_pilot_competency_review_decision
    FROM kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT (
    reviewer_operator_id, reviewer_party_id, request_id, location_id,
    draft_id, decision, reason, created_at
)
ON TABLE public.operating_pilot_competency_review_decision
TO kokonut_operating_pilot_reader;
GRANT INSERT (
    reviewer_operator_id, reviewer_party_id, request_id, location_id,
    draft_id, decision, reason
)
ON TABLE public.operating_pilot_competency_review_decision
TO kokonut_operating_pilot_reader;

CREATE INDEX IF NOT EXISTS idx_operating_competency_submitted_review
    ON public.operating_pilot_competency_draft(updated_at DESC, id DESC)
    WHERE status = 'submitted';

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_competency_review_queue(
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
    reviewer_party_ids UUID[];
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Competency review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Competency review queue requires an exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Competency review page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT array_agg(binding.party_id ORDER BY binding.party_id)
      INTO reviewer_party_ids
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF coalesce(cardinality(reviewer_party_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Competency review requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;

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
        SELECT draft.id, draft.competency_key, draft.current_level,
               draft.target_level, draft.evidence_note, draft.updated_at
          FROM public.operating_pilot_competency_draft AS draft
         WHERE draft.location_id = requested_location_id
           AND draft.status = 'submitted'
           AND draft.party_id <> reviewer_party_ids[1]
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
                 FROM public.operating_pilot_competency_draft_receipt AS creation
                 JOIN public.operating_pilot_competency_submission_receipt AS submission
                   ON submission.draft_id = creation.draft_id
                  AND submission.operator_id = creation.operator_id
                  AND submission.location_id = creation.location_id
                WHERE creation.draft_id = draft.id
                  AND creation.operator_id = draft.operator_id
                  AND creation.location_id = draft.location_id
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
                           'competency_key', page.competency_key,
                           'current_level', page.current_level,
                           'target_level', page.target_level,
                           'evidence_note', page.evidence_note,
                           'status', 'submitted',
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

ALTER FUNCTION kokonut_security.location_operating_pilot_competency_review_queue(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_competency_review_queue(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_competency_review_queue(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_operating_pilot_competency(
    requested_location_id UUID,
    requested_draft_id UUID,
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
    reviewer_party_ids UUID[] := ARRAY[]::UUID[];
    reviewer_party_id UUID;
    pilot_scope_id UUID;
    normalized_reason TEXT := NULLIF(
        btrim(requested_reason, ' ' || chr(9) || chr(10) || chr(13)), ''
    );
    existing_decision RECORD;
    draft_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_draft_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Competency review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Competency review requires an active exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL
       OR requested_decision NOT IN ('verified', 'rejected')
       OR requested_reason IS NOT NULL AND char_length(requested_reason) > 2000
       OR requested_decision = 'rejected' AND normalized_reason IS NULL
       OR requested_decision = 'verified' AND normalized_reason IS NOT NULL THEN
        RAISE EXCEPTION 'Competency review decision or reason is invalid'
            USING ERRCODE = '22023';
    END IF;

    FOR binding_record IN
        SELECT binding.party_id
          FROM public.operator_governance_party_binding AS binding
          JOIN public.operator_identity AS operator
            ON operator.id = binding.operator_id AND operator.enabled
          JOIN public.party AS reviewer
            ON reviewer.id = binding.party_id
           AND reviewer.party_type = 'person'
           AND reviewer.status = 'active'
         WHERE binding.operator_id = context_record.actor_id
           AND binding.revoked_at IS NULL
         FOR SHARE OF binding, operator, reviewer
    LOOP
        reviewer_party_ids := array_append(reviewer_party_ids, binding_record.party_id);
    END LOOP;
    IF cardinality(reviewer_party_ids) <> 1 THEN
        RAISE EXCEPTION 'Competency review requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    reviewer_party_id := reviewer_party_ids[1];

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

    PERFORM pg_advisory_xact_lock(
        hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0)
    );
    SELECT decision.location_id, decision.draft_id, decision.decision, decision.reason
      INTO existing_decision
      FROM public.operating_pilot_competency_review_decision AS decision
     WHERE decision.reviewer_operator_id = context_record.actor_id
       AND decision.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_decision.location_id IS DISTINCT FROM requested_location_id
           OR existing_decision.draft_id IS DISTINCT FROM requested_draft_id
           OR existing_decision.decision IS DISTINCT FROM requested_decision
           OR existing_decision.reason IS DISTINCT FROM normalized_reason THEN
            RAISE EXCEPTION 'Competency review request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN jsonb_build_object(
            'draft_id', requested_draft_id,
            'status', existing_decision.decision,
            'decision', existing_decision.decision,
            'replayed', TRUE
        );
    END IF;

    SELECT draft.id, draft.party_id, draft.status
      INTO draft_record
      FROM public.operating_pilot_competency_draft AS draft
     WHERE draft.id = requested_draft_id
       AND draft.location_id = requested_location_id
       AND draft.scope_id = pilot_scope_id
       AND draft.status = 'submitted'
       AND EXISTS (
           SELECT 1
             FROM public.operating_pilot_competency_draft_receipt AS creation
             JOIN public.operating_pilot_competency_submission_receipt AS submission
               ON submission.draft_id = creation.draft_id
              AND submission.operator_id = creation.operator_id
              AND submission.location_id = creation.location_id
            WHERE creation.draft_id = draft.id
              AND creation.operator_id = draft.operator_id
              AND creation.location_id = draft.location_id
       )
     FOR UPDATE OF draft;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submitted competency assessment is unavailable for review'
            USING ERRCODE = '42501';
    END IF;
    IF draft_record.party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Competency reviewers cannot review their own submissions'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.operating_pilot_competency_draft
       SET status = requested_decision, updated_at = clock_timestamp()
     WHERE id = requested_draft_id AND status = 'submitted';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Competency assessment changed before review decision'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_pilot_competency_review_decision (
        reviewer_operator_id, reviewer_party_id, request_id, location_id,
        draft_id, decision, reason
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_request_id,
        requested_location_id, requested_draft_id, requested_decision,
        normalized_reason
    );

    RETURN jsonb_build_object(
        'draft_id', requested_draft_id,
        'status', requested_decision,
        'decision', requested_decision,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.review_location_operating_pilot_competency(
    UUID, UUID, UUID, TEXT, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.review_location_operating_pilot_competency(
    UUID, UUID, UUID, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.review_location_operating_pilot_competency(
    UUID, UUID, UUID, TEXT, TEXT
) TO kokonut_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_own_competency_drafts(
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
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Own competency read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'read_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Own competency read requires an exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Own competency page is outside its bounds'
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
        RAISE EXCEPTION 'Own competency read requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;

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

    WITH selected AS (
        SELECT draft.id, draft.competency_key, draft.current_level,
               draft.target_level, draft.evidence_note, draft.status,
               draft.created_at, draft.updated_at,
               decision.reason AS review_reason,
               decision.created_at AS reviewed_at
          FROM public.operating_pilot_competency_draft AS draft
          LEFT JOIN public.operating_pilot_competency_review_decision AS decision
            ON decision.draft_id = draft.id
         WHERE draft.operator_id = context_record.actor_id
           AND draft.location_id = requested_location_id
           AND draft.party_id = actor_party_ids[1]
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
                 FROM public.operating_pilot_competency_draft_receipt AS receipt
                WHERE receipt.operator_id = draft.operator_id
                  AND receipt.location_id = draft.location_id
                  AND receipt.draft_id = draft.id
           )
         ORDER BY draft.created_at DESC, draft.id DESC
         LIMIT requested_limit + 1 OFFSET requested_offset
    ), page AS (
        SELECT selected.*,
               row_number() OVER (ORDER BY selected.created_at DESC, selected.id DESC) AS page_row
          FROM selected
    ), page_result AS (
        SELECT coalesce(
                   jsonb_agg(
                       jsonb_build_object(
                           'draft_id', page.id,
                           'competency_key', page.competency_key,
                           'current_level', page.current_level,
                           'target_level', page.target_level,
                           'evidence_note', page.evidence_note,
                           'status', page.status,
                           'review_reason', page.review_reason,
                           'reviewed_at', page.reviewed_at,
                           'created_at', page.created_at,
                           'updated_at', page.updated_at
                       ) ORDER BY page.page_row
                   ) FILTER (WHERE page.page_row <= requested_limit),
                   '[]'::JSONB
               ) AS items,
               count(*) > requested_limit AS has_more
          FROM page
    )
    SELECT jsonb_build_object(
        'limit', requested_limit,
        'offset', requested_offset,
        'items', page_result.items,
        'has_more', page_result.has_more,
        'next_offset', CASE
            WHEN page_result.has_more THEN requested_offset + requested_limit
            ELSE NULL
        END
    ) INTO result
      FROM page_result;

    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_own_competency_drafts(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_own_competency_drafts(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_own_competency_drafts(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;

REVOKE ALL ON TABLE public.operating_pilot_competency_review_decision
    FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE UPDATE, DELETE ON TABLE public.operating_pilot_competency_review_decision
    FROM kokonut_operating_pilot_reader;

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_competency_review_queue(
    UUID, INTEGER, INTEGER
) IS 'Returns a bounded exact-location queue of receipt-backed submitted competency assessments for independent review, excluding the reviewer own party.';
COMMENT ON FUNCTION kokonut_security.review_location_operating_pilot_competency(
    UUID, UUID, UUID, TEXT, TEXT
) IS 'Records one exact-location independent verified/rejected decision for a submitted receipt-backed competency assessment, prohibits self-review, and preserves exact retry receipts.';
COMMENT ON TABLE public.operating_pilot_competency_review_decision IS
'Append-only private audit and idempotency record for a human competency assessment review; rejection reason is returned only to the submitting operator own-history path.';

COMMIT;
