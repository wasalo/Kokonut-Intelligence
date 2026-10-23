-- Show authenticated operator draft creators and their opaque idempotency
-- request IDs in the exact-location AI-summary review queue.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_reviewer'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_runtime'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'directus'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_task_summary_writer'
    ) THEN
        RAISE EXCEPTION 'AI summary operator attribution role prerequisites are missing';
    END IF;
END;
$$;

-- The reviewer can correlate a queue row to its authenticated request, but
-- cannot inspect its payload, hash, or other request history. Application,
-- Directus, and task-writer roles receive no receipt access.
REVOKE ALL ON TABLE public.ai_summary_draft_request
    FROM PUBLIC, kokonut_ai_summary_reviewer, kokonut_runtime,
         directus, kokonut_agent_task_summary_writer;
REVOKE SELECT (
    operator_id, request_id, location_id, summary_type, request_hash,
    summary_id, created_at
) ON TABLE public.ai_summary_draft_request
    FROM PUBLIC, kokonut_ai_summary_reviewer, kokonut_runtime,
         directus, kokonut_agent_task_summary_writer;
GRANT SELECT (operator_id, request_id, location_id, summary_id)
    ON TABLE public.ai_summary_draft_request
    TO kokonut_ai_summary_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_ai_summary_reviews_with_creator(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    summary_id UUID,
    summary_type TEXT,
    content TEXT,
    content_truncated BOOLEAN,
    source_tables TEXT[],
    model_version TEXT,
    created_at TIMESTAMPTZ,
    review_ready BOOLEAN,
    blocked_reasons TEXT[],
    source_references JSONB,
    creator_task_key TEXT,
    creator_run_id UUID,
    creator_kind TEXT,
    creator_operator_id UUID,
    creator_request_id UUID
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    RETURN QUERY
    SELECT review.summary_id,
           review.summary_type,
           review.content,
           review.content_truncated,
           review.source_tables,
           review.model_version,
           review.created_at,
           review.review_ready,
           review.blocked_reasons,
           review.source_references,
           review.creator_task_key,
           review.creator_run_id,
           CASE
               WHEN review.creator_task_key = 'unregistered_worker'
                   THEN 'unregistered_worker'::TEXT
               WHEN review.creator_task_key IS NOT NULL
                   THEN 'registered_worker'::TEXT
               WHEN operator_request.request_id IS NOT NULL
                   THEN 'operator'::TEXT
               ELSE 'unattributed'::TEXT
           END,
           CASE WHEN operator_request.request_id IS NOT NULL
                THEN summary.created_by END,
           operator_request.request_id
      FROM kokonut_security.list_location_ai_summary_reviews_with_worker_run(
               requested_location_id, requested_limit, requested_offset
           ) AS review
      JOIN public.ai_summary AS summary
        ON summary.id = review.summary_id
       AND summary.subject_type = 'location'
       AND summary.subject_id = requested_location_id
      LEFT JOIN public.ai_summary_draft_request AS operator_request
        ON operator_request.summary_id = summary.id
       AND operator_request.location_id = requested_location_id
       AND operator_request.operator_id = summary.created_by;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_creator(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_creator(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_creator(
    UUID, INTEGER, INTEGER
) FROM directus, kokonut_agent_task_summary_writer;
ALTER FUNCTION kokonut_security.list_location_ai_summary_reviews_with_creator(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_ai_summary_reviewer;

DO $$
BEGIN
    IF pg_catalog.has_table_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_draft_request', 'SELECT'
       )
       OR NOT pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_draft_request', 'operator_id', 'SELECT'
       )
       OR NOT pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_draft_request', 'request_id', 'SELECT'
       )
       OR pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_draft_request', 'request_hash', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_runtime', 'public.ai_summary_draft_request', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'directus', 'public.ai_summary_draft_request', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_agent_task_summary_writer',
           'public.ai_summary_draft_request', 'SELECT'
       )
       OR EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                  COALESCE(relation.relacl, pg_catalog.acldefault('r', relation.relowner))
              ) AS acl
             WHERE relation.oid = pg_catalog.to_regclass('public.ai_summary_draft_request')
               AND acl.grantee = 0
               AND acl.privilege_type = 'SELECT'
       )
       OR pg_catalog.has_function_privilege(
           'directus',
           'kokonut_security.list_location_ai_summary_reviews_with_creator(uuid,integer,integer)',
           'EXECUTE'
       )
       OR NOT pg_catalog.has_function_privilege(
           'kokonut_runtime',
           'kokonut_security.list_location_ai_summary_reviews_with_creator(uuid,integer,integer)',
           'EXECUTE'
       ) THEN
        RAISE EXCEPTION 'AI summary creator attribution privileges exceed the review contract';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_creator(
    UUID, INTEGER, INTEGER
) IS
    'Returns location-authorized AI-summary reviews with registered worker task/run IDs or authenticated operator/request UUIDs; never returns request payloads, hashes, or operator profile details.';

COMMIT;
