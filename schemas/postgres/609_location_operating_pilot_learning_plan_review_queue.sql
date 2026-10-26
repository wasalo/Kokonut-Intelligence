-- Expose submitted, receipt-backed learning plans to independent location reviewers.

BEGIN;

CREATE INDEX IF NOT EXISTS idx_operating_pilot_learning_plan_submission_plan_created
    ON public.operating_pilot_learning_plan_submission_receipt
       (learning_plan_id, created_at DESC, request_id DESC);

REVOKE ALL ON TABLE public.operating_learning_plan,
    public.operating_pilot_learning_plan_draft_receipt,
    public.operating_pilot_learning_plan_submission_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
DO $$
DECLARE column_name TEXT;
        table_name TEXT;
        role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        FOREACH table_name IN ARRAY ARRAY[
            'operating_learning_plan',
            'operating_pilot_learning_plan_draft_receipt',
            'operating_pilot_learning_plan_submission_receipt'
        ] LOOP
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = pg_catalog.to_regclass('public.' || table_name)
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE ALL (%1$I) ON TABLE public.%2$I FROM %3$I',
                    column_name, table_name, role_name
                );
            END LOOP;
        END LOOP;
    END LOOP;
END;
$$;

GRANT SELECT (
    id, party_id, scope_type, scope_id, title, competency_goals,
    support_requested, target_date, status, updated_at
) ON TABLE public.operating_learning_plan TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, learning_plan_id)
    ON TABLE public.operating_pilot_learning_plan_draft_receipt
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, learning_plan_id, created_at)
    ON TABLE public.operating_pilot_learning_plan_submission_receipt
    TO kokonut_operating_pilot_reader;

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
               plan.updated_at
          FROM public.operating_learning_plan AS plan
          JOIN public.operating_pilot_learning_plan_draft_receipt AS draft
            ON draft.learning_plan_id = plan.id
           AND draft.location_id = requested_location_id
          JOIN LATERAL (
              SELECT submitted.operator_id
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
                           'updated_at', page.updated_at
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

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_learning_plan_review_queue(
    UUID, INTEGER, INTEGER
) IS 'Returns a bounded exact-location queue of receipt-backed submitted learning plans, excludes the reviewer own party, and omits identities and internal scope.';

COMMIT;
