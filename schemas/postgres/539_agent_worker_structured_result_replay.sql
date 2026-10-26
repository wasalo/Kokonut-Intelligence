-- Persist the complete worker response alongside its draft so exact retries
-- can return the original structured output without rerunning source queries.

BEGIN;

CREATE TABLE IF NOT EXISTS kokonut_security.ai_summary_agent_draft_result (
    worker_id UUID NOT NULL,
    request_id UUID NOT NULL,
    result_payload JSONB NOT NULL
        CHECK (pg_catalog.jsonb_typeof(result_payload) = 'object')
        CHECK (pg_catalog.octet_length(result_payload::TEXT) <= 131072),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (worker_id, request_id),
    FOREIGN KEY (worker_id, request_id)
        REFERENCES public.ai_summary_agent_draft_request (worker_id, request_id)
        ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_ai_summary_agent_draft_result_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'AI summary agent draft results are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_summary_agent_draft_result_immutable
    ON kokonut_security.ai_summary_agent_draft_result;
CREATE TRIGGER trg_ai_summary_agent_draft_result_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.ai_summary_agent_draft_result
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_ai_summary_agent_draft_result_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.get_location_ai_summary_worker_result(
    requested_location_id UUID,
    requested_summary_type TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    summary_id UUID,
    content TEXT,
    source_tables TEXT[],
    model_version TEXT,
    created_at TIMESTAMPTZ,
    resulting_status TEXT,
    worker_result JSONB
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    existing_record RECORD;
BEGIN
    SELECT scope.actor_id, scope.location_id
      INTO context_record
      FROM kokonut_security.current_worker_scope('ai_summary', 'draft') AS scope;
    IF context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL
       OR requested_summary_type IS NULL
       OR requested_summary_type !~ '^[a-z][a-z0-9_]{0,99}$' THEN
        RAISE EXCEPTION 'AI summary worker result requires signed exact-location draft scope'
            USING ERRCODE = '42501';
    END IF;

    SELECT draft_request.location_id, draft_request.summary_type
      INTO existing_record
      FROM public.ai_summary_agent_draft_request AS draft_request
     WHERE draft_request.worker_id = context_record.actor_id
       AND draft_request.request_id = requested_request_id;
    IF FOUND AND (
        existing_record.location_id IS DISTINCT FROM requested_location_id
        OR existing_record.summary_type IS DISTINCT FROM requested_summary_type
    ) THEN
        RAISE EXCEPTION 'AI summary worker request identifier was reused for another intent'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT summary.id, summary.content::TEXT, summary.source_tables,
           summary.model_version::TEXT, summary.created_at, summary.status::TEXT,
           draft_result.result_payload
      FROM public.ai_summary_agent_draft_request AS draft_request
      JOIN public.ai_summary AS summary
        ON summary.id = draft_request.summary_id
      LEFT JOIN kokonut_security.ai_summary_agent_draft_result AS draft_result
        ON draft_result.worker_id = draft_request.worker_id
       AND draft_result.request_id = draft_request.request_id
     WHERE draft_request.worker_id = context_record.actor_id
       AND draft_request.request_id = requested_request_id
       AND draft_request.location_id = requested_location_id
       AND draft_request.summary_type = requested_summary_type
       AND summary.subject_type = 'location'
       AND summary.subject_id = requested_location_id
       AND summary.created_by IS NULL
       AND summary.created_by_worker_id = context_record.actor_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_ai_summary_worker_draft_with_result(
    requested_location_id UUID,
    requested_summary_type TEXT,
    requested_content TEXT,
    requested_source_tables TEXT[],
    requested_model_version TEXT,
    requested_request_id UUID,
    requested_worker_result JSONB
)
RETURNS TABLE (
    summary_id UUID,
    content TEXT,
    source_tables TEXT[],
    model_version TEXT,
    created_at TIMESTAMPTZ,
    resulting_status TEXT,
    replayed BOOLEAN,
    worker_result JSONB
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    draft_record RECORD;
    stored_result JSONB;
BEGIN
    IF requested_worker_result IS NULL
       OR pg_catalog.jsonb_typeof(requested_worker_result) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(requested_worker_result::TEXT) > 131072 THEN
        RAISE EXCEPTION 'AI summary worker result payload is invalid'
            USING ERRCODE = '22023';
    END IF;
    IF (
           NOT (requested_worker_result ? 'content')
       AND NOT (requested_worker_result ? 'synthesis')
    ) OR (
           requested_worker_result ? 'content'
       AND requested_worker_result ->> 'content' IS DISTINCT FROM requested_content
    ) OR (
           requested_worker_result ? 'synthesis'
       AND requested_worker_result ->> 'synthesis' IS DISTINCT FROM requested_content
    ) THEN
        RAISE EXCEPTION 'AI summary worker result must match the stored draft content'
            USING ERRCODE = '22023';
    END IF;

    SELECT * INTO STRICT draft_record
      FROM kokonut_security.create_location_ai_summary_worker_draft(
          requested_location_id, requested_summary_type, requested_content,
          requested_source_tables, requested_model_version, requested_request_id
      );

    IF NOT draft_record.replayed THEN
        INSERT INTO kokonut_security.ai_summary_agent_draft_result (
            worker_id, request_id, result_payload
        )
        SELECT scope.actor_id, requested_request_id, requested_worker_result
          FROM kokonut_security.current_worker_scope('ai_summary', 'draft') AS scope
         WHERE scope.location_id = requested_location_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'AI summary worker result requires signed exact-location draft scope'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    SELECT draft_result.result_payload INTO stored_result
      FROM kokonut_security.ai_summary_agent_draft_result AS draft_result
      JOIN public.ai_summary_agent_draft_request AS draft_request
        ON draft_request.worker_id = draft_result.worker_id
       AND draft_request.request_id = draft_result.request_id
     WHERE draft_request.worker_id = (
               SELECT scope.actor_id
                 FROM kokonut_security.current_worker_scope('ai_summary', 'draft') AS scope
                WHERE scope.location_id = requested_location_id
           )
       AND draft_request.request_id = requested_request_id
       AND draft_request.location_id = requested_location_id
       AND draft_request.summary_type = requested_summary_type;

    RETURN QUERY SELECT draft_record.summary_id, draft_record.content,
                        draft_record.source_tables, draft_record.model_version,
                        draft_record.created_at, draft_record.resulting_status,
                        draft_record.replayed, stored_result;
END;
$$;

REVOKE ALL ON TABLE kokonut_security.ai_summary_agent_draft_result FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.prevent_ai_summary_agent_draft_result_mutation()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_ai_summary_worker_result(UUID, TEXT, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.create_location_ai_summary_worker_draft_with_result(
    UUID, TEXT, TEXT, TEXT[], TEXT, UUID, JSONB
) FROM PUBLIC;

GRANT SELECT, INSERT ON TABLE kokonut_security.ai_summary_agent_draft_result
    TO kokonut_ai_summary_drafter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_ai_summary_drafter;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.prevent_ai_summary_agent_draft_result_mutation()
    OWNER TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.get_location_ai_summary_worker_result(UUID, TEXT, UUID)
    OWNER TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.create_location_ai_summary_worker_draft_with_result(
    UUID, TEXT, TEXT, TEXT[], TEXT, UUID, JSONB
) OWNER TO kokonut_ai_summary_drafter;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_ai_summary_drafter;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_worker_execution') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_ai_summary_worker_result(
            UUID, TEXT, UUID
        ) TO kokonut_worker_execution;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_ai_summary_worker_draft_with_result(
            UUID, TEXT, TEXT, TEXT[], TEXT, UUID, JSONB
        ) TO kokonut_worker_execution;
        REVOKE ALL ON TABLE kokonut_security.ai_summary_agent_draft_result
            FROM kokonut_worker_execution;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.ai_summary_agent_draft_result
            FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.get_location_ai_summary_worker_result(
            UUID, TEXT, UUID
        ) FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.create_location_ai_summary_worker_draft_with_result(
            UUID, TEXT, TEXT, TEXT[], TEXT, UUID, JSONB
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'directus') THEN
        REVOKE ALL ON TABLE kokonut_security.ai_summary_agent_draft_result FROM directus;
        REVOKE ALL ON FUNCTION kokonut_security.get_location_ai_summary_worker_result(
            UUID, TEXT, UUID
        ) FROM directus;
        REVOKE ALL ON FUNCTION kokonut_security.create_location_ai_summary_worker_draft_with_result(
            UUID, TEXT, TEXT, TEXT[], TEXT, UUID, JSONB
        ) FROM directus;
    END IF;
END;
$$;

COMMENT ON TABLE kokonut_security.ai_summary_agent_draft_result IS
    'Private append-only structured worker result paired atomically with its immutable AI-summary draft request receipt.';

COMMIT;
