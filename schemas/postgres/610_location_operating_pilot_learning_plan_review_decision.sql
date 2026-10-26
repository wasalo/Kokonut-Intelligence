-- Record an independent learning-plan review outcome without conflating approval and activation.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_pilot_learning_plan_review_decision (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    reviewer_operator_id UUID NOT NULL
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    learning_plan_id UUID NOT NULL
        REFERENCES public.operating_learning_plan(id) ON DELETE RESTRICT,
    submission_created_at TIMESTAMPTZ NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reason TEXT,
    resulting_status TEXT NOT NULL CHECK (resulting_status IN ('submitted', 'draft')),
    input_digest BYTEA NOT NULL
        CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (reviewer_operator_id, request_id),
    UNIQUE (learning_plan_id, submission_created_at),
    CHECK (reason IS NULL OR pg_catalog.char_length(reason) <= 2000),
    CHECK (
        (decision = 'approved' AND reason IS NULL AND resulting_status = 'submitted')
        OR (decision = 'rejected' AND reason IS NOT NULL AND resulting_status = 'draft')
    ),
    CHECK (
        reason IS NULL OR NULLIF(
            pg_catalog.btrim(
                reason,
                ' ' || pg_catalog.chr(9) || pg_catalog.chr(10) || pg_catalog.chr(13)
            ),
            ''
        ) IS NOT NULL
    )
);

REVOKE ALL ON TABLE public.operating_pilot_learning_plan_review_decision
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime,
         kokonut_operating_pilot_reader;
DO $$
DECLARE column_name TEXT;
        role_name TEXT;
BEGIN
    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid =
               'public.operating_pilot_learning_plan_review_decision'::REGCLASS
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ALL (%1$I) ON TABLE public.operating_pilot_learning_plan_review_decision FROM PUBLIC',
            column_name
        );
    END LOOP;
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_operating_pilot_reader'
    ] LOOP
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid =
                   'public.operating_pilot_learning_plan_review_decision'::REGCLASS
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE ALL (%1$I) ON TABLE public.operating_pilot_learning_plan_review_decision FROM %2$I',
                column_name, role_name
            );
        END LOOP;
    END LOOP;
END;
$$;
GRANT SELECT (
    reviewer_operator_id, reviewer_party_id, request_id, location_id,
    learning_plan_id, submission_created_at, decision, reason, resulting_status,
    input_digest, created_at
) ON TABLE public.operating_pilot_learning_plan_review_decision
    TO kokonut_operating_pilot_reader;
GRANT INSERT (
    reviewer_operator_id, reviewer_party_id, request_id, location_id,
    learning_plan_id, submission_created_at, decision, reason, resulting_status,
    input_digest
) ON TABLE public.operating_pilot_learning_plan_review_decision
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_operating_pilot_reader;

CREATE INDEX IF NOT EXISTS idx_operating_pilot_learning_plan_review_decision_plan
    ON public.operating_pilot_learning_plan_review_decision
       (learning_plan_id, submission_created_at DESC);

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_learning_plan_review_queue(
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
    reviewer_party_id UUID;
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Learning-plan review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan review queue requires an exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Learning-plan review page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT pg_catalog.array_agg(binding.party_id ORDER BY binding.party_id)
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
    IF coalesce(pg_catalog.cardinality(reviewer_party_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Learning-plan review requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    reviewer_party_id := reviewer_party_ids[1];

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
        SELECT plan.id, plan.title, plan.competency_goals,
               plan.support_requested, plan.target_date, plan.status,
               plan.updated_at, submission.created_at AS submitted_at
          FROM public.operating_learning_plan AS plan
          JOIN public.operating_pilot_learning_plan_draft_receipt AS draft
            ON draft.learning_plan_id = plan.id
           AND draft.location_id = requested_location_id
          JOIN LATERAL (
              SELECT submitted.operator_id, submitted.created_at,
                     submitted.request_id
                FROM public.operating_pilot_learning_plan_submission_receipt AS submitted
               WHERE submitted.learning_plan_id = plan.id
                 AND submitted.location_id = requested_location_id
                 AND submitted.operator_id = draft.operator_id
               ORDER BY submitted.created_at DESC, submitted.request_id DESC
               LIMIT 1
          ) AS submission ON TRUE
         WHERE plan.scope_type = 'adelphi'
           AND plan.status = 'submitted'
           AND plan.party_id <> reviewer_party_id
           AND NOT EXISTS (
               SELECT 1
                 FROM public.operating_pilot_learning_plan_review_decision AS decision
                WHERE decision.learning_plan_id = plan.id
                  AND decision.submission_created_at = submission.created_at
           )
           AND EXISTS (
               SELECT 1
                 FROM public.operating_pilot_scope AS scope
                 JOIN public.farm AS pilot_farm
                   ON pilot_farm.id = scope.scope_id
                  AND pilot_farm.location_id = requested_location_id
                  AND pilot_farm.status = 'active'
                WHERE scope.scope_type = 'adelphi'
                  AND scope.status = 'active'
                  AND scope.scope_id = plan.scope_id
           )
    ), selected AS (
        SELECT *
          FROM eligible
         ORDER BY updated_at DESC, id DESC
         LIMIT requested_limit + 1 OFFSET requested_offset
    ), page AS (
        SELECT selected.*,
               pg_catalog.row_number() OVER (ORDER BY selected.updated_at DESC, selected.id DESC) AS page_row
          FROM selected
    ), page_result AS (
        SELECT coalesce(
                   pg_catalog.jsonb_agg(
                       pg_catalog.jsonb_build_object(
                           'learning_plan_id', page.id,
                           'title', page.title,
                           'competency_goals', page.competency_goals,
                           'support_requested', page.support_requested,
                           'target_date', page.target_date,
                           'status', 'submitted',
                           'updated_at', page.updated_at,
                           'submitted_at', page.submitted_at
                       ) ORDER BY page.page_row
                   ) FILTER (WHERE page.page_row <= requested_limit),
                   '[]'::jsonb
               ) AS items,
               count(*) > requested_limit AS has_more
          FROM page
    )
    SELECT pg_catalog.jsonb_build_object(
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

ALTER FUNCTION kokonut_security.location_operating_pilot_learning_plan_review_queue(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_learning_plan_review_queue(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_learning_plan_review_queue(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_learning_plan_review_queue(
    UUID, INTEGER, INTEGER
) FROM kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_operating_pilot_learning_plan(
    requested_location_id UUID,
    requested_learning_plan_id UUID,
    requested_request_id UUID,
    requested_submission_created_at TIMESTAMPTZ,
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
        pg_catalog.btrim(
            requested_reason,
            ' ' || pg_catalog.chr(9) || pg_catalog.chr(10) || pg_catalog.chr(13)
        ),
        ''
    );
    input_digest BYTEA;
    existing_decision RECORD;
    target_record RECORD;
    resulting_status TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_learning_plan_id IS NULL
       OR requested_request_id IS NULL
       OR requested_submission_created_at IS NULL THEN
        RAISE EXCEPTION 'Learning-plan review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan review requires an active exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL
       OR requested_decision NOT IN ('approved', 'rejected')
       OR requested_reason IS NOT NULL AND pg_catalog.char_length(requested_reason) > 2000
       OR requested_decision = 'rejected' AND normalized_reason IS NULL
       OR requested_decision = 'approved' AND normalized_reason IS NOT NULL THEN
        RAISE EXCEPTION 'Learning-plan review decision or reason is invalid'
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
        reviewer_party_ids := pg_catalog.array_append(reviewer_party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(reviewer_party_ids) <> 1 THEN
        RAISE EXCEPTION 'Learning-plan review requires exactly one active human-party binding'
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
     ORDER BY scope.id
     LIMIT 1
     FOR KEY SHARE OF scope, pilot_farm;
    IF pilot_scope_id IS NULL THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                requested_learning_plan_id::TEXT,
                requested_submission_created_at,
                requested_decision,
                normalized_reason
            )::TEXT,
            'UTF8'
        ),
        'sha256'::TEXT
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT decision.location_id, decision.learning_plan_id,
           decision.submission_created_at, decision.decision,
           decision.reason, decision.resulting_status
      INTO existing_decision
      FROM public.operating_pilot_learning_plan_review_decision AS decision
     WHERE decision.reviewer_operator_id = context_record.actor_id
       AND decision.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_decision.location_id IS DISTINCT FROM requested_location_id
           OR existing_decision.learning_plan_id IS DISTINCT FROM requested_learning_plan_id
           OR existing_decision.submission_created_at IS DISTINCT FROM requested_submission_created_at
           OR existing_decision.decision IS DISTINCT FROM requested_decision
           OR existing_decision.reason IS DISTINCT FROM normalized_reason THEN
            RAISE EXCEPTION 'Learning-plan review request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'learning_plan_id', existing_decision.learning_plan_id,
            'decision', existing_decision.decision,
            'status', existing_decision.resulting_status,
            'replayed', TRUE
        );
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.operating_pilot_learning_plan_draft_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) OR EXISTS (
        SELECT 1 FROM public.operating_pilot_learning_plan_revision_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) OR EXISTS (
        SELECT 1 FROM public.operating_pilot_learning_plan_submission_receipt AS receipt
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan review request ID conflicts with another operation'
            USING ERRCODE = '23505';
    END IF;

    SELECT plan.party_id, submission.created_at
      INTO target_record
      FROM public.operating_learning_plan AS plan
      JOIN public.operating_pilot_learning_plan_draft_receipt AS draft
        ON draft.learning_plan_id = plan.id
       AND draft.location_id = requested_location_id
      JOIN LATERAL (
          SELECT receipt.operator_id, receipt.request_id, receipt.created_at
            FROM public.operating_pilot_learning_plan_submission_receipt AS receipt
           WHERE receipt.learning_plan_id = plan.id
             AND receipt.location_id = requested_location_id
             AND receipt.operator_id = draft.operator_id
           ORDER BY receipt.created_at DESC, receipt.request_id DESC
           LIMIT 1
      ) AS submission ON TRUE
     WHERE plan.id = requested_learning_plan_id
       AND plan.scope_type = 'adelphi'
       AND plan.scope_id = pilot_scope_id
       AND plan.status = 'submitted'
       AND submission.created_at = requested_submission_created_at
     FOR UPDATE OF plan;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Learning-plan submission is stale or unavailable for review'
            USING ERRCODE = '40001';
    END IF;
    IF target_record.party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Learning-plan review cannot decide the reviewer own submission'
            USING ERRCODE = '42501';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM public.operating_pilot_learning_plan_review_decision AS decision
         WHERE decision.learning_plan_id = requested_learning_plan_id
           AND decision.submission_created_at = requested_submission_created_at
    ) THEN
        RAISE EXCEPTION 'This learning-plan submission already has a decision'
            USING ERRCODE = '23505';
    END IF;

    resulting_status := CASE requested_decision
        WHEN 'approved' THEN 'submitted'
        ELSE 'draft'
    END;
    IF requested_decision = 'rejected' THEN
        UPDATE public.operating_learning_plan
           SET status = 'draft', updated_at = pg_catalog.clock_timestamp()
         WHERE id = requested_learning_plan_id AND status = 'submitted';
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Learning-plan submission changed before review'
                USING ERRCODE = '40001';
        END IF;
    END IF;

    INSERT INTO public.operating_pilot_learning_plan_review_decision (
        reviewer_operator_id, reviewer_party_id, request_id, location_id,
        learning_plan_id, submission_created_at, decision, reason,
        resulting_status, input_digest
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_request_id,
        requested_location_id, requested_learning_plan_id,
        requested_submission_created_at, requested_decision, normalized_reason,
        resulting_status, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'learning_plan_id', requested_learning_plan_id,
        'decision', requested_decision,
        'status', resulting_status,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.review_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.review_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.review_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.review_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) FROM kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_own_learning_plans(
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
        RAISE EXCEPTION 'Own learning-plan read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'read_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Own learning-plan read requires an exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Own learning-plan page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT pg_catalog.array_agg(binding.party_id ORDER BY binding.party_id)
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
    IF coalesce(pg_catalog.cardinality(actor_party_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Own learning-plan read requires exactly one active human-party binding'
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
        SELECT plan.id, plan.title, plan.competency_goals,
               plan.support_requested, plan.target_date, plan.status,
               plan.created_at, plan.updated_at
          FROM public.operating_learning_plan AS plan
         WHERE plan.party_id = actor_party_ids[1]
           AND plan.scope_type = 'adelphi'
           AND EXISTS (
               SELECT 1
                 FROM public.operating_pilot_scope AS scope
                 JOIN public.farm AS pilot_farm
                   ON pilot_farm.id = scope.scope_id
                  AND pilot_farm.location_id = requested_location_id
                  AND pilot_farm.status = 'active'
                WHERE scope.scope_type = 'adelphi'
                  AND scope.status = 'active'
                  AND scope.scope_id = plan.scope_id
           )
         ORDER BY plan.created_at DESC, plan.id DESC
         LIMIT requested_limit + 1 OFFSET requested_offset
    ), page AS (
        SELECT selected.*,
               pg_catalog.row_number() OVER (ORDER BY selected.created_at DESC, selected.id DESC) AS page_row
          FROM selected
    ), decisions AS (
        SELECT page.*,
               latest_decision.decision AS review_decision,
               latest_decision.reason AS review_reason,
               latest_decision.created_at AS reviewed_at
          FROM page
          LEFT JOIN LATERAL (
              SELECT decision.decision, decision.reason, decision.created_at
                FROM public.operating_pilot_learning_plan_submission_receipt AS submission
                LEFT JOIN public.operating_pilot_learning_plan_review_decision AS decision
                  ON decision.learning_plan_id = submission.learning_plan_id
                 AND decision.submission_created_at = submission.created_at
               WHERE submission.learning_plan_id = page.id
                 AND submission.operator_id = context_record.actor_id
                 AND submission.location_id = requested_location_id
               ORDER BY submission.created_at DESC, submission.request_id DESC
               LIMIT 1
          ) AS latest_decision ON TRUE
    ), page_result AS (
        SELECT coalesce(
                   pg_catalog.jsonb_agg(
                       pg_catalog.jsonb_build_object(
                           'learning_plan_id', decisions.id,
                           'title', decisions.title,
                           'competency_goals', decisions.competency_goals,
                           'support_requested', decisions.support_requested,
                           'target_date', decisions.target_date,
                           'status', decisions.status,
                           'review_decision', decisions.review_decision,
                           'review_reason', decisions.review_reason,
                           'reviewed_at', decisions.reviewed_at,
                           'created_at', decisions.created_at,
                           'updated_at', decisions.updated_at
                       ) ORDER BY decisions.page_row
                   ) FILTER (WHERE decisions.page_row <= requested_limit),
                   '[]'::JSONB
               ) AS items,
               count(*) > requested_limit AS has_more
          FROM decisions
    )
    SELECT pg_catalog.jsonb_build_object(
        'limit', requested_limit,
        'offset', requested_offset,
        'items', page_result.items,
        'has_more', page_result.has_more,
        'next_offset', CASE
            WHEN page_result.has_more THEN requested_offset + requested_limit
            ELSE NULL
        END
    )
      INTO result
      FROM page_result;
    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_own_learning_plans(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_own_learning_plans(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_own_learning_plans(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_own_learning_plans(
    UUID, INTEGER, INTEGER
) FROM kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.review_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) IS 'Records one independent decision for the exact latest receipt-backed submitted learning-plan version; approval does not activate the plan, and rejection returns it to draft.';
COMMENT ON TABLE public.operating_pilot_learning_plan_review_decision IS
'Private append-only learning-plan reviewer decision and retry ledger. Approval remains separate from activation; a rejection includes feedback for the submitting owner.';

COMMIT;
