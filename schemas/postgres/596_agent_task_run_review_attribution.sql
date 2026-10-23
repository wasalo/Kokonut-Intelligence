-- Expose the authenticated worker request ID beside its registered task in
-- the exact-location human review queue.

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
    ) THEN
        RAISE EXCEPTION 'AI summary review role prerequisites are missing';
    END IF;
END;
$$;

-- The non-login reviewer function owner receives only the three columns
-- needed to correlate a location-scoped review row with its opaque request ID.
-- The application/runtime roles never receive direct access to this table.
REVOKE ALL ON TABLE public.ai_summary_agent_draft_request
    FROM kokonut_runtime, directus, kokonut_agent_task_summary_writer;
REVOKE SELECT (
    worker_id, request_id, location_id, summary_type, request_hash, summary_id, created_at
) ON TABLE public.ai_summary_agent_draft_request
    FROM kokonut_runtime, directus, kokonut_agent_task_summary_writer;
REVOKE ALL ON TABLE public.ai_summary_agent_draft_request
    FROM kokonut_ai_summary_reviewer;
REVOKE SELECT (
    worker_id, request_id, location_id, summary_type, request_hash, summary_id, created_at
) ON TABLE public.ai_summary_agent_draft_request
    FROM kokonut_ai_summary_reviewer;
GRANT SELECT (request_id, summary_id, location_id)
    ON TABLE public.ai_summary_agent_draft_request
    TO kokonut_ai_summary_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_run(
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
    creator_run_id UUID
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
           request.request_id
      FROM kokonut_security.list_location_ai_summary_reviews_with_worker_task(
               requested_location_id, requested_limit, requested_offset
           ) AS review
      LEFT JOIN public.ai_summary_agent_draft_request AS request
        ON request.summary_id = review.summary_id
       AND request.location_id = requested_location_id
     ORDER BY review.created_at ASC, review.summary_id ASC;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_run(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_run(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_run(
    UUID, INTEGER, INTEGER
) FROM directus, kokonut_agent_task_summary_writer;
ALTER FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_run(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_ai_summary_reviewer;

DO $$
BEGIN
    IF NOT pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_agent_draft_request', 'request_id', 'SELECT'
       )
       OR NOT pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_agent_draft_request', 'summary_id', 'SELECT'
       )
       OR NOT pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_agent_draft_request', 'location_id', 'SELECT'
       )
       OR pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_agent_draft_request', 'request_hash', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_ai_summary_reviewer',
           'public.ai_summary_agent_draft_request', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_runtime',
           'public.ai_summary_agent_draft_request', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'directus',
           'public.ai_summary_agent_draft_request', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_agent_task_summary_writer',
           'public.ai_summary_agent_draft_request', 'SELECT'
       )
       OR pg_catalog.has_function_privilege(
           'directus',
           'kokonut_security.list_location_ai_summary_reviews_with_worker_run(uuid,integer,integer)',
           'EXECUTE'
       )
       OR NOT pg_catalog.has_function_privilege(
           'kokonut_runtime',
           'kokonut_security.list_location_ai_summary_reviews_with_worker_run(uuid,integer,integer)',
           'EXECUTE'
       ) THEN
        RAISE EXCEPTION 'worker run attribution privileges exceed the scoped reviewer contract';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_run(
    UUID, INTEGER, INTEGER
) IS
    'Returns the bounded exact-location AI summary review queue with authenticated task and opaque worker request ID attribution; no request payload or cross-location receipt is exposed.';

COMMIT;
