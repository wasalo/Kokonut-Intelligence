-- Bind registered agent-task drafts to an exact authenticated operator request.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_drafter'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_task_summary_writer'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_runtime'
    ) THEN
        RAISE EXCEPTION 'authenticated agent-task request role prerequisites are missing';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.ai_summary_worker_task_summary_type (
    task_key TEXT NOT NULL
        REFERENCES kokonut_security.ai_summary_worker_task_registry(task_key)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    summary_type TEXT NOT NULL
        CHECK (summary_type ~ '^[a-z][a-z0-9_]{0,99}$'),
    PRIMARY KEY (task_key, summary_type)
);

INSERT INTO kokonut_security.ai_summary_worker_task_summary_type (task_key, summary_type)
VALUES
    ('ai_summary_synthesis', 'operations'),
    ('ai_summary_synthesis', 'financial'),
    ('ai_summary_synthesis', 'environmental'),
    ('ai_summary_synthesis', 'combined'),
    ('organic_readiness_synthesis', 'organic_readiness'),
    ('ecological_modeling_synthesis', 'ecological_modeling'),
    ('holistic_wellbeing_synthesis', 'holistic_wellbeing'),
    ('feedback_synthesis', 'stakeholder_feedback'),
    ('commons_liberation_synthesis', 'commons_liberation'),
    ('gnh_alignment_synthesis', 'gnh_alignment'),
    ('regenerator_synthesis', 'regenerative_outcomes'),
    ('capital_efficiency_synthesis', 'capital_efficiency'),
    ('financial_resilience_synthesis', 'financial_resilience'),
    ('bio_factory_synthesis', 'bio_factory'),
    ('open_source_capitalist_synthesis', 'open_source_capitalist'),
    ('kokonut_commons_synthesis', 'kokonut_commons')
ON CONFLICT (task_key, summary_type) DO NOTHING;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM (VALUES
              ('ai_summary_synthesis', 'operations'),
              ('ai_summary_synthesis', 'financial'),
              ('ai_summary_synthesis', 'environmental'),
              ('ai_summary_synthesis', 'combined'),
              ('organic_readiness_synthesis', 'organic_readiness'),
              ('ecological_modeling_synthesis', 'ecological_modeling'),
              ('holistic_wellbeing_synthesis', 'holistic_wellbeing'),
              ('feedback_synthesis', 'stakeholder_feedback'),
              ('commons_liberation_synthesis', 'commons_liberation'),
              ('gnh_alignment_synthesis', 'gnh_alignment'),
              ('regenerator_synthesis', 'regenerative_outcomes'),
              ('capital_efficiency_synthesis', 'capital_efficiency'),
              ('financial_resilience_synthesis', 'financial_resilience'),
              ('bio_factory_synthesis', 'bio_factory'),
              ('open_source_capitalist_synthesis', 'open_source_capitalist'),
              ('kokonut_commons_synthesis', 'kokonut_commons')
          ) AS expected(task_key, summary_type)
          LEFT JOIN kokonut_security.ai_summary_worker_task_summary_type AS actual
            ON actual.task_key = expected.task_key
           AND actual.summary_type = expected.summary_type
         WHERE actual.task_key IS NULL
    ) THEN
        RAISE EXCEPTION 'registered agent task summary-type contract is incomplete';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.ai_summary_operator_task_request (
    request_id UUID PRIMARY KEY,
    operator_id UUID NOT NULL
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL
        REFERENCES public.location(id) ON DELETE RESTRICT,
    task_key TEXT NOT NULL,
    summary_type TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    FOREIGN KEY (task_key, summary_type)
        REFERENCES kokonut_security.ai_summary_worker_task_summary_type(task_key, summary_type)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION public.prevent_ai_summary_operator_task_request_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'AI-summary operator task requests are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_summary_operator_task_request_immutable
    ON kokonut_security.ai_summary_operator_task_request;
CREATE TRIGGER trg_ai_summary_operator_task_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.ai_summary_operator_task_request
    FOR EACH ROW EXECUTE FUNCTION public.prevent_ai_summary_operator_task_request_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.create_location_ai_summary_operator_task_request(
    requested_location_id UUID,
    requested_task_key TEXT,
    requested_summary_type TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    request_id UUID,
    location_id UUID,
    task_key TEXT,
    summary_type TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    existing_record RECORD;
    request_hash_value TEXT;
    created_at_value TIMESTAMPTZ := pg_catalog.clock_timestamp();
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR NOT public.operator_scope_grant_allows(
            context_record.actor_id, 'ai_summary', 'draft', requested_location_id
       ) THEN
        RAISE EXCEPTION 'agent-task request requires a signed operator ai_summary:draft scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL
       OR requested_task_key IS NULL
       OR requested_summary_type IS NULL
       OR NOT EXISTS (
            SELECT 1
              FROM kokonut_security.ai_summary_worker_task_summary_type AS allowed
             WHERE allowed.task_key = requested_task_key
               AND allowed.summary_type = requested_summary_type
       ) THEN
        RAISE EXCEPTION 'registered agent-task request fields are invalid'
            USING ERRCODE = '22023';
    END IF;

    request_hash_value := pg_catalog.encode(
        public.digest(
            pg_catalog.convert_to(
                pg_catalog.jsonb_build_object(
                    'operator_id', context_record.actor_id,
                    'location_id', requested_location_id,
                    'task_key', requested_task_key,
                    'summary_type', requested_summary_type
                )::TEXT,
                'UTF8'
            ),
            'sha256'
        ),
        'hex'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(requested_request_id::TEXT, 0)
    );

    SELECT receipt.operator_id, receipt.location_id, receipt.task_key,
           receipt.summary_type, receipt.request_hash, receipt.created_at
      INTO existing_record
      FROM kokonut_security.ai_summary_operator_task_request AS receipt
     WHERE receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_record.operator_id IS DISTINCT FROM context_record.actor_id
           OR existing_record.location_id IS DISTINCT FROM requested_location_id
           OR existing_record.task_key IS DISTINCT FROM requested_task_key
           OR existing_record.summary_type IS DISTINCT FROM requested_summary_type
           OR existing_record.request_hash IS DISTINCT FROM request_hash_value THEN
            RAISE EXCEPTION 'agent-task request ID was reused for another intent'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT requested_request_id, requested_location_id,
                            requested_task_key, requested_summary_type,
                            existing_record.created_at, TRUE;
        RETURN;
    END IF;

    INSERT INTO kokonut_security.ai_summary_operator_task_request (
        request_id, operator_id, location_id, task_key, summary_type, request_hash,
        created_at
    ) VALUES (
        requested_request_id, context_record.actor_id, requested_location_id,
        requested_task_key, requested_summary_type, request_hash_value,
        created_at_value
    );
    RETURN QUERY SELECT requested_request_id, requested_location_id,
                        requested_task_key, requested_summary_type,
                        created_at_value, FALSE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.verify_current_ai_summary_operator_task_request(
    requested_location_id UUID,
    requested_summary_type TEXT,
    requested_request_id UUID
)
RETURNS TABLE (task_key TEXT, operator_id UUID)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    authenticated_task_key TEXT;
    attributed_task_key TEXT;
    receipt RECORD;
BEGIN
    IF pg_catalog.current_setting('role', TRUE)
       IS DISTINCT FROM 'kokonut_agent_task_summary_writer' THEN
        RAISE EXCEPTION 'operator task verification requires the function-only task writer role'
            USING ERRCODE = '42501';
    END IF;
    SELECT scope.actor_id, scope.location_id
      INTO context_record
      FROM kokonut_security.current_worker_scope('ai_summary', 'draft') AS scope;
    IF context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_summary_type IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'operator task request requires signed worker location scope'
            USING ERRCODE = '42501';
    END IF;

    SELECT registry.task_key INTO authenticated_task_key
      FROM kokonut_security.ai_summary_worker_task_registry AS registry
     WHERE registry.login_role = SESSION_USER::TEXT;
    SELECT attribution.task_key INTO attributed_task_key
      FROM kokonut_security.ai_summary_worker_task_attribution AS attribution
     WHERE attribution.worker_id = context_record.actor_id;
    IF authenticated_task_key IS NULL
       OR attributed_task_key IS DISTINCT FROM authenticated_task_key THEN
        RAISE EXCEPTION 'worker task identity is not registered for operator attribution'
            USING ERRCODE = '42501';
    END IF;

    SELECT request.operator_id, request.location_id, request.task_key,
           request.summary_type
      INTO receipt
      FROM kokonut_security.ai_summary_operator_task_request AS request
     WHERE request.request_id = requested_request_id;
    IF NOT FOUND
       OR receipt.location_id IS DISTINCT FROM requested_location_id
       OR receipt.task_key IS DISTINCT FROM authenticated_task_key
       OR receipt.summary_type IS DISTINCT FROM requested_summary_type
       OR NOT EXISTS (
            SELECT 1
              FROM kokonut_security.ai_summary_worker_task_summary_type AS allowed
             WHERE allowed.task_key = authenticated_task_key
               AND allowed.summary_type = requested_summary_type
       )
       OR NOT public.operator_scope_grant_allows(
            receipt.operator_id, 'ai_summary', 'draft', requested_location_id
       ) THEN
        RAISE EXCEPTION 'an active matching authenticated operator task request is required'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY SELECT authenticated_task_key, receipt.operator_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.require_ai_summary_operator_task_request()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
BEGIN
    IF pg_catalog.current_setting('role', TRUE)
       IS DISTINCT FROM 'kokonut_agent_task_summary_writer' THEN
        RETURN NEW;
    END IF;

    SELECT scope.actor_id, scope.location_id
      INTO context_record
      FROM kokonut_security.current_worker_scope('ai_summary', 'draft') AS scope;
    IF context_record.actor_id IS NULL
       OR context_record.actor_id IS DISTINCT FROM NEW.worker_id
       OR context_record.location_id IS DISTINCT FROM NEW.location_id THEN
        RAISE EXCEPTION 'task draft receipt does not match its signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    PERFORM 1
      FROM kokonut_security.verify_current_ai_summary_operator_task_request(
          NEW.location_id, NEW.summary_type, NEW.request_id
      );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_summary_agent_operator_task_request
    ON public.ai_summary_agent_draft_request;
CREATE TRIGGER trg_ai_summary_agent_operator_task_request
    BEFORE INSERT ON public.ai_summary_agent_draft_request
    FOR EACH ROW EXECUTE FUNCTION public.require_ai_summary_operator_task_request();

-- The independent review queue can attribute operator-started worker drafts
-- without granting runtime, Directus, or task workers general receipt access.
REVOKE ALL ON TABLE kokonut_security.ai_summary_operator_task_request
    FROM kokonut_ai_summary_reviewer;
REVOKE SELECT (request_id, operator_id, location_id, task_key, summary_type,
               request_hash, created_at)
    ON TABLE kokonut_security.ai_summary_operator_task_request
    FROM kokonut_ai_summary_reviewer;
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
               WHEN task_request.request_id IS NOT NULL
                   THEN 'operator_task'::TEXT
               WHEN review.creator_task_key IS NOT NULL
                   THEN 'registered_worker'::TEXT
               WHEN operator_request.request_id IS NOT NULL
                   THEN 'operator'::TEXT
               ELSE 'unattributed'::TEXT
           END,
           CASE
               WHEN task_request.request_id IS NOT NULL THEN task_request.operator_id
               WHEN operator_request.request_id IS NOT NULL THEN summary.created_by
           END,
           COALESCE(operator_request.request_id, task_request.request_id)
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
       AND operator_request.operator_id = summary.created_by
      LEFT JOIN kokonut_security.ai_summary_operator_task_request AS task_request
        ON task_request.request_id = review.creator_run_id
       AND task_request.location_id = requested_location_id
       AND task_request.task_key = review.creator_task_key
       AND task_request.summary_type = summary.summary_type::TEXT;
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

REVOKE ALL ON TABLE kokonut_security.ai_summary_worker_task_summary_type,
    kokonut_security.ai_summary_operator_task_request FROM PUBLIC;
REVOKE ALL ON TABLE kokonut_security.ai_summary_worker_task_summary_type,
    kokonut_security.ai_summary_operator_task_request
    FROM kokonut_runtime, directus, kokonut_worker_execution,
         kokonut_agent_task_summary_writer, kokonut_ai_summary_reviewer;
GRANT SELECT (request_id, operator_id, location_id, task_key, summary_type)
    ON TABLE kokonut_security.ai_summary_operator_task_request
    TO kokonut_ai_summary_reviewer;
GRANT SELECT ON TABLE kokonut_security.ai_summary_worker_task_summary_type,
    kokonut_security.ai_summary_operator_task_request TO kokonut_ai_summary_drafter;
GRANT INSERT ON TABLE kokonut_security.ai_summary_operator_task_request
    TO kokonut_ai_summary_drafter;

REVOKE ALL ON FUNCTION public.prevent_ai_summary_operator_task_request_mutation()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION public.require_ai_summary_operator_task_request() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.create_location_ai_summary_operator_task_request(
    UUID, TEXT, TEXT, UUID
) FROM PUBLIC, directus, kokonut_agent_task_summary_writer,
         kokonut_worker_execution, kokonut_ai_summary_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.verify_current_ai_summary_operator_task_request(
    UUID, TEXT, UUID
) FROM PUBLIC, directus, kokonut_runtime, kokonut_worker_execution,
         kokonut_ai_summary_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_ai_summary_drafter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_ai_summary_drafter;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_ai_summary_drafter;
GRANT EXECUTE ON FUNCTION kokonut_security.create_location_ai_summary_operator_task_request(
    UUID, TEXT, TEXT, UUID
) TO kokonut_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.verify_current_ai_summary_operator_task_request(
    UUID, TEXT, UUID
) TO kokonut_agent_task_summary_writer;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_ai_summary_drafter;
GRANT CREATE ON SCHEMA public TO kokonut_ai_summary_drafter;
ALTER FUNCTION public.prevent_ai_summary_operator_task_request_mutation()
    OWNER TO kokonut_ai_summary_drafter;
ALTER FUNCTION public.require_ai_summary_operator_task_request()
    OWNER TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.create_location_ai_summary_operator_task_request(
    UUID, TEXT, TEXT, UUID
) OWNER TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.verify_current_ai_summary_operator_task_request(
    UUID, TEXT, UUID
) OWNER TO kokonut_ai_summary_drafter;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_ai_summary_drafter;
REVOKE CREATE ON SCHEMA public FROM kokonut_ai_summary_drafter;

DO $$
BEGIN
    IF pg_catalog.has_table_privilege(
           'kokonut_runtime',
           'kokonut_security.ai_summary_operator_task_request', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'directus',
           'kokonut_security.ai_summary_operator_task_request', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_agent_task_summary_writer',
           'kokonut_security.ai_summary_operator_task_request', 'SELECT'
       )
       OR pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'kokonut_security.ai_summary_operator_task_request', 'request_hash', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_ai_summary_reviewer',
           'kokonut_security.ai_summary_operator_task_request', 'SELECT'
       )
       OR NOT pg_catalog.has_column_privilege(
           'kokonut_ai_summary_reviewer',
           'kokonut_security.ai_summary_operator_task_request', 'operator_id', 'SELECT'
       )
       OR pg_catalog.has_function_privilege(
           'directus',
           'kokonut_security.create_location_ai_summary_operator_task_request(uuid,text,text,uuid)',
           'EXECUTE'
       )
       OR NOT pg_catalog.has_function_privilege(
           'kokonut_runtime',
           'kokonut_security.create_location_ai_summary_operator_task_request(uuid,text,text,uuid)',
           'EXECUTE'
       )
       OR NOT pg_catalog.has_function_privilege(
           'kokonut_agent_task_summary_writer',
           'kokonut_security.verify_current_ai_summary_operator_task_request(uuid,text,uuid)',
           'EXECUTE'
       ) THEN
        RAISE EXCEPTION 'authenticated agent-task request grants exceed their bounded function contracts (runtime-select=%, directus-select=%, task-writer-select=%, reviewer-hash=%, reviewer-table=%, reviewer-operator=%, directus-create=%, runtime-create=%, task-writer-verify=%)',
            pg_catalog.has_table_privilege(
                'kokonut_runtime',
                'kokonut_security.ai_summary_operator_task_request', 'SELECT'
            ),
            pg_catalog.has_table_privilege(
                'directus',
                'kokonut_security.ai_summary_operator_task_request', 'SELECT'
            ),
            pg_catalog.has_table_privilege(
                'kokonut_agent_task_summary_writer',
                'kokonut_security.ai_summary_operator_task_request', 'SELECT'
            ),
            pg_catalog.has_column_privilege(
                'kokonut_ai_summary_reviewer',
                'kokonut_security.ai_summary_operator_task_request', 'request_hash', 'SELECT'
            ),
            pg_catalog.has_table_privilege(
                'kokonut_ai_summary_reviewer',
                'kokonut_security.ai_summary_operator_task_request', 'SELECT'
            ),
            pg_catalog.has_column_privilege(
                'kokonut_ai_summary_reviewer',
                'kokonut_security.ai_summary_operator_task_request', 'operator_id', 'SELECT'
            ),
            pg_catalog.has_function_privilege(
                'directus',
                'kokonut_security.create_location_ai_summary_operator_task_request(uuid,text,text,uuid)',
                'EXECUTE'
            ),
            pg_catalog.has_function_privilege(
                'kokonut_runtime',
                'kokonut_security.create_location_ai_summary_operator_task_request(uuid,text,text,uuid)',
                'EXECUTE'
            ),
            pg_catalog.has_function_privilege(
                'kokonut_agent_task_summary_writer',
                'kokonut_security.verify_current_ai_summary_operator_task_request(uuid,text,uuid)',
                'EXECUTE'
            );
    END IF;
END;
$$;

COMMENT ON TABLE kokonut_security.ai_summary_operator_task_request IS
    'Immutable, opaque operator authorization receipts binding one registered synthesis task and summary type to one exact location.';
COMMENT ON FUNCTION kokonut_security.create_location_ai_summary_operator_task_request(UUID, TEXT, TEXT, UUID) IS
    'Creates or replays an immutable task request only under signed operator ai_summary:draft scope; does not execute, verify, or publish the resulting summary.';
COMMENT ON FUNCTION kokonut_security.verify_current_ai_summary_operator_task_request(UUID, TEXT, UUID) IS
    'Verifies task-writer identity, signed location, exact task/summary binding, and the current initiating operator draft grant before a task draft write.';
COMMENT ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_creator(UUID, INTEGER, INTEGER) IS
    'Returns exact-location human review rows with worker task/run and authenticated initiating-operator attribution; request hashes and operator profile data remain private.';

COMMIT;
