-- Activate only an independently approved, exact-location learning-plan submission.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_pilot_learning_plan_activation_receipt (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    learning_plan_id UUID NOT NULL
        REFERENCES public.operating_learning_plan(id) ON DELETE RESTRICT,
    submission_created_at TIMESTAMPTZ NOT NULL,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (operator_id, request_id),
    UNIQUE (learning_plan_id, submission_created_at)
);

REVOKE ALL ON TABLE public.operating_pilot_learning_plan_activation_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime,
         kokonut_operating_pilot_reader;
DO $$
DECLARE column_name TEXT;
        role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_operating_pilot_reader'
    ] LOOP
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid =
                   'public.operating_pilot_learning_plan_activation_receipt'::REGCLASS
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            IF role_name = 'PUBLIC' THEN
                EXECUTE pg_catalog.format(
                    'REVOKE ALL (%1$I) ON TABLE public.operating_pilot_learning_plan_activation_receipt FROM PUBLIC',
                    column_name
                );
            ELSE
                EXECUTE pg_catalog.format(
                    'REVOKE ALL (%1$I) ON TABLE public.operating_pilot_learning_plan_activation_receipt FROM %2$I',
                    column_name, role_name
                );
            END IF;
        END LOOP;
    END LOOP;
END;
$$;

GRANT SELECT (
    operator_id, actor_party_id, request_id, location_id, learning_plan_id,
    submission_created_at, input_digest, created_at
) ON TABLE public.operating_pilot_learning_plan_activation_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (
    operator_id, actor_party_id, request_id, location_id, learning_plan_id,
    submission_created_at, input_digest
) ON TABLE public.operating_pilot_learning_plan_activation_receipt
    TO kokonut_operating_pilot_reader;

CREATE INDEX IF NOT EXISTS idx_operating_pilot_learning_plan_activation_queue
    ON public.operating_pilot_learning_plan_activation_receipt
       (location_id, created_at DESC, learning_plan_id);

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_learning_plan_activation_queue(
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
        RAISE EXCEPTION 'Learning-plan activation queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'activate', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan activation queue requires an exact location activation grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Learning-plan activation page is outside its bounds'
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
        RAISE EXCEPTION 'Learning-plan activation requires exactly one active human-party binding'
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
        SELECT plan.id, plan.title, plan.competency_goals,
               plan.support_requested, plan.target_date, plan.updated_at,
               submission.created_at AS submitted_at,
               decision.created_at AS approved_at
          FROM public.operating_learning_plan AS plan
          JOIN public.operating_pilot_learning_plan_draft_receipt AS draft
            ON draft.learning_plan_id = plan.id
           AND draft.location_id = requested_location_id
          JOIN LATERAL (
              SELECT receipt.operator_id, receipt.created_at, receipt.request_id
                FROM public.operating_pilot_learning_plan_submission_receipt AS receipt
               WHERE receipt.learning_plan_id = plan.id
                 AND receipt.location_id = requested_location_id
                 AND receipt.operator_id = draft.operator_id
               ORDER BY receipt.created_at DESC, receipt.request_id DESC
               LIMIT 1
          ) AS submission ON TRUE
          JOIN public.operating_pilot_learning_plan_review_decision AS decision
            ON decision.learning_plan_id = plan.id
           AND decision.submission_created_at = submission.created_at
           AND decision.decision = 'approved'
         WHERE plan.scope_type = 'adelphi'
           AND plan.status = 'submitted'
           AND plan.party_id <> actor_party_id
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
           AND NOT EXISTS (
               SELECT 1
                 FROM public.operating_pilot_learning_plan_activation_receipt AS activation
                WHERE activation.learning_plan_id = plan.id
                  AND activation.submission_created_at = submission.created_at
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
                           'submitted_at', page.submitted_at,
                           'approved_at', page.approved_at
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

ALTER FUNCTION kokonut_security.location_operating_pilot_learning_plan_activation_queue(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_learning_plan_activation_queue(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_learning_plan_activation_queue(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_learning_plan_activation_queue(
    UUID, INTEGER, INTEGER
) FROM kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.activate_location_operating_pilot_learning_plan(
    requested_location_id UUID,
    requested_learning_plan_id UUID,
    requested_request_id UUID,
    requested_submission_created_at TIMESTAMPTZ
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
    actor_party_ids UUID[] := ARRAY[]::UUID[];
    actor_party_id UUID;
    pilot_scope_id UUID;
    target_record RECORD;
    existing_activation RECORD;
    input_digest BYTEA;
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
        RAISE EXCEPTION 'Learning-plan activation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'activate', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan activation requires an active exact location grant'
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
        actor_party_ids := pg_catalog.array_append(actor_party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(actor_party_ids) <> 1 THEN
        RAISE EXCEPTION 'Learning-plan activation requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    actor_party_id := actor_party_ids[1];

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
                requested_submission_created_at
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

    SELECT activation.location_id, activation.learning_plan_id,
           activation.submission_created_at, activation.input_digest
      INTO existing_activation
      FROM public.operating_pilot_learning_plan_activation_receipt AS activation
     WHERE activation.operator_id = context_record.actor_id
       AND activation.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_activation.location_id IS DISTINCT FROM requested_location_id
           OR existing_activation.learning_plan_id IS DISTINCT FROM requested_learning_plan_id
           OR existing_activation.submission_created_at IS DISTINCT FROM requested_submission_created_at
           OR existing_activation.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Learning-plan activation request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'learning_plan_id', existing_activation.learning_plan_id,
            'status', 'active',
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
    ) OR EXISTS (
        SELECT 1 FROM public.operating_pilot_learning_plan_review_decision AS receipt
         WHERE receipt.reviewer_operator_id = context_record.actor_id
           AND receipt.request_id = requested_request_id
    ) THEN
        RAISE EXCEPTION 'Learning-plan activation request ID conflicts with another operation'
            USING ERRCODE = '23505';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.operating_pilot_learning_plan_activation_receipt AS activation
         WHERE activation.learning_plan_id = requested_learning_plan_id
           AND activation.submission_created_at = requested_submission_created_at
    ) THEN
        RAISE EXCEPTION 'This approved learning-plan submission was already activated'
            USING ERRCODE = '23505';
    END IF;

    SELECT plan.party_id, plan.status
      INTO target_record
      FROM public.operating_learning_plan AS plan
      JOIN public.operating_pilot_learning_plan_draft_receipt AS draft
        ON draft.learning_plan_id = plan.id
       AND draft.location_id = requested_location_id
      JOIN LATERAL (
          SELECT receipt.operator_id, receipt.created_at, receipt.request_id
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
       AND EXISTS (
           SELECT 1
             FROM public.operating_pilot_learning_plan_review_decision AS decision
            WHERE decision.learning_plan_id = plan.id
              AND decision.submission_created_at = submission.created_at
              AND decision.decision = 'approved'
       )
     FOR UPDATE OF plan;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Learning plan is stale or has no approved submission for activation'
            USING ERRCODE = '40001';
    END IF;
    IF target_record.party_id = actor_party_id THEN
        RAISE EXCEPTION 'Learning-plan owners cannot activate their own plan'
            USING ERRCODE = '42501';
    END IF;
    UPDATE public.operating_learning_plan
       SET status = 'active', updated_at = pg_catalog.clock_timestamp()
     WHERE id = requested_learning_plan_id AND status = 'submitted';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Learning plan changed before activation'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.operating_pilot_learning_plan_activation_receipt (
        operator_id, actor_party_id, request_id, location_id,
        learning_plan_id, submission_created_at, input_digest
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_request_id,
        requested_location_id, requested_learning_plan_id,
        requested_submission_created_at, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'learning_plan_id', requested_learning_plan_id,
        'status', 'active',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.activate_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.activate_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.activate_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.activate_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ
) FROM kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_learning_plan_activation_queue(
    UUID, INTEGER, INTEGER
) IS 'Returns a bounded exact-location queue of other-party learning plans whose latest receipt-backed submission was approved and remains submitted.';
COMMENT ON FUNCTION kokonut_security.activate_location_operating_pilot_learning_plan(
    UUID, UUID, UUID, TIMESTAMPTZ
) IS 'Activates one independently approved exact-location learning-plan submission under a separate activate grant and immutable idempotency receipt.';

COMMIT;
