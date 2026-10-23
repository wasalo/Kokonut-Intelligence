-- Allow registered, task-scoped source identities to create their own drafts
-- and expose that authenticated identity to independent human reviewers.

BEGIN;

DO $$
DECLARE
    task_writer_oid OID;
    worker_execution_oid OID;
    identity RECORD;
    login_oid OID;
    reader_oid OID;
    unexpected_membership TEXT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_task_summary_writer'
    ) THEN
        CREATE ROLE kokonut_agent_task_summary_writer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_task_summary_writer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'agent task summary writer role has unsafe attributes';
    END IF;

    SELECT oid INTO task_writer_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = 'kokonut_agent_task_summary_writer';
    SELECT oid INTO worker_execution_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = 'kokonut_worker_execution';
    IF task_writer_oid IS NULL OR worker_execution_oid IS NULL THEN
        RAISE EXCEPTION 'agent task summary writer prerequisites are missing';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
         WHERE membership.member = task_writer_oid
    ) THEN
        RAISE EXCEPTION 'agent task summary writer must not inherit another role';
    END IF;

    FOR identity IN
        SELECT * FROM (VALUES
            ('kokonut_agent_summary_deterministic_source_login',
             'kokonut_agent_summary_deterministic_reader'),
            ('kokonut_agent_organic_readiness_login',
             'kokonut_agent_organic_readiness_reader'),
            ('kokonut_agent_ecological_modeling_login',
             'kokonut_agent_ecological_modeling_reader'),
            ('kokonut_agent_holistic_wellbeing_login',
             'kokonut_agent_holistic_wellbeing_reader'),
            ('kokonut_agent_feedback_login',
             'kokonut_agent_feedback_reader'),
            ('kokonut_agent_commons_liberation_login',
             'kokonut_agent_commons_liberation_reader'),
            ('kokonut_agent_gnh_alignment_login',
             'kokonut_agent_gnh_alignment_reader'),
            ('kokonut_agent_regenerator_login',
             'kokonut_agent_regenerator_reader'),
            ('kokonut_agent_capital_efficiency_login',
             'kokonut_agent_capital_efficiency_reader'),
            ('kokonut_agent_financial_resilience_login',
             'kokonut_agent_financial_resilience_reader'),
            ('kokonut_agent_bio_factory_login',
             'kokonut_agent_bio_factory_reader'),
            ('kokonut_agent_open_source_capitalist_login',
             'kokonut_agent_open_source_capitalist_reader'),
            ('kokonut_agent_kokonut_commons_login',
             'kokonut_agent_kokonut_commons_reader')
        ) AS registered(login_name, reader_name)
    LOOP
        SELECT oid INTO login_oid FROM pg_catalog.pg_roles
         WHERE rolname = identity.login_name;
        SELECT oid INTO reader_oid FROM pg_catalog.pg_roles
         WHERE rolname = identity.reader_name;
        IF login_oid IS NULL OR reader_oid IS NULL THEN
            RAISE EXCEPTION 'agent task source role pair is missing: %', identity.login_name;
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE oid = login_oid
               AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                    OR rolbypassrls OR rolinherit)
        ) OR EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE oid = reader_oid
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'agent task source role pair has unsafe attributes: %',
                identity.login_name;
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_auth_members AS membership
             WHERE membership.roleid = worker_execution_oid
               AND membership.member = login_oid
        ) THEN
            RAISE EXCEPTION 'task-scoped source login must not inherit broad worker execution: %',
                identity.login_name;
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_auth_members AS membership
             WHERE membership.roleid = reader_oid
               AND membership.member = login_oid
               AND (membership.admin_option OR membership.inherit_option
                    OR NOT membership.set_option)
        ) OR NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_auth_members AS membership
             WHERE membership.roleid = reader_oid
               AND membership.member = login_oid
               AND NOT membership.admin_option
               AND NOT membership.inherit_option
               AND membership.set_option
        ) THEN
            RAISE EXCEPTION 'agent task source reader membership is invalid: %',
                identity.login_name;
        END IF;
    END LOOP;

    SELECT pg_catalog.string_agg(member_role.rolname, ', ' ORDER BY member_role.rolname)
      INTO unexpected_membership
      FROM pg_catalog.pg_auth_members AS membership
      JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
     WHERE membership.roleid = task_writer_oid
       AND member_role.rolname NOT IN (
           'kokonut_agent_summary_deterministic_source_login',
           'kokonut_agent_organic_readiness_login',
           'kokonut_agent_ecological_modeling_login',
           'kokonut_agent_holistic_wellbeing_login',
           'kokonut_agent_feedback_login',
           'kokonut_agent_commons_liberation_login',
           'kokonut_agent_gnh_alignment_login',
           'kokonut_agent_regenerator_login',
           'kokonut_agent_capital_efficiency_login',
           'kokonut_agent_financial_resilience_login',
           'kokonut_agent_bio_factory_login',
           'kokonut_agent_open_source_capitalist_login',
           'kokonut_agent_kokonut_commons_login'
       );
    IF unexpected_membership IS NOT NULL THEN
        RAISE EXCEPTION 'agent task summary writer has unexpected login members: %',
            unexpected_membership;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security TO kokonut_agent_task_summary_writer;
REVOKE CREATE ON SCHEMA public, kokonut_security
    FROM kokonut_agent_task_summary_writer;
REVOKE ALL ON ALL TABLES IN SCHEMA public, kokonut_security
    FROM kokonut_agent_task_summary_writer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public, kokonut_security
    FROM kokonut_agent_task_summary_writer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public, kokonut_security
    FROM kokonut_agent_task_summary_writer;

GRANT EXECUTE ON FUNCTION kokonut_security.create_location_ai_summary_worker_draft(
    UUID, TEXT, TEXT, TEXT[], TEXT, UUID
) TO kokonut_agent_task_summary_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.create_location_ai_summary_worker_draft_with_result(
    UUID, TEXT, TEXT, TEXT[], TEXT, UUID, JSONB
) TO kokonut_agent_task_summary_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.get_location_ai_summary_worker_result(
    UUID, TEXT, UUID
) TO kokonut_agent_task_summary_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.set_location_ai_summary_source_references(
    UUID, UUID, UUID, JSONB
) TO kokonut_agent_task_summary_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.get_location_ai_summary_worker_source_references(
    UUID, UUID, UUID
) TO kokonut_agent_task_summary_writer;

DO $$
BEGIN
    IF pg_catalog.has_table_privilege(
           'kokonut_agent_task_summary_writer', 'public.ai_summary', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_agent_task_summary_writer', 'public.ai_summary', 'INSERT'
       )
       OR pg_catalog.has_function_privilege(
           'kokonut_agent_task_summary_writer',
           'kokonut_security.get_location_ai_summary_worker_draft_request(uuid,text,uuid)',
           'EXECUTE'
       )
       OR pg_catalog.has_schema_privilege(
           'kokonut_agent_task_summary_writer', 'public', 'CREATE'
       )
       OR pg_catalog.has_schema_privilege(
           'kokonut_agent_task_summary_writer', 'kokonut_security', 'CREATE'
       ) THEN
        RAISE EXCEPTION 'agent task summary writer exceeds its function-only privilege contract';
    END IF;
END;
$$;

GRANT kokonut_agent_task_summary_writer TO
    kokonut_agent_summary_deterministic_source_login,
    kokonut_agent_organic_readiness_login,
    kokonut_agent_ecological_modeling_login,
    kokonut_agent_holistic_wellbeing_login,
    kokonut_agent_feedback_login,
    kokonut_agent_commons_liberation_login,
    kokonut_agent_gnh_alignment_login,
    kokonut_agent_regenerator_login,
    kokonut_agent_capital_efficiency_login,
    kokonut_agent_financial_resilience_login,
    kokonut_agent_bio_factory_login,
    kokonut_agent_open_source_capitalist_login,
    kokonut_agent_kokonut_commons_login
    WITH INHERIT FALSE, SET TRUE;

CREATE TABLE IF NOT EXISTS kokonut_security.ai_summary_worker_task_registry (
    principal_key TEXT PRIMARY KEY
        CHECK (principal_key ~ '^agent-[a-z0-9-]{1,80}$'),
    task_key TEXT NOT NULL UNIQUE
        CHECK (task_key ~ '^[a-z][a-z0-9_]{1,79}$'),
    login_role TEXT NOT NULL UNIQUE
        CHECK (login_role ~ '^kokonut_agent_[a-z0-9_]{1,80}_login$')
);

INSERT INTO kokonut_security.ai_summary_worker_task_registry (principal_key, task_key, login_role)
VALUES
    ('agent-summary-deterministic-source', 'ai_summary_synthesis', 'kokonut_agent_summary_deterministic_source_login'),
    ('agent-organic-readiness-source', 'organic_readiness_synthesis', 'kokonut_agent_organic_readiness_login'),
    ('agent-ecological-modeling-source', 'ecological_modeling_synthesis', 'kokonut_agent_ecological_modeling_login'),
    ('agent-holistic-wellbeing-source', 'holistic_wellbeing_synthesis', 'kokonut_agent_holistic_wellbeing_login'),
    ('agent-feedback-source', 'feedback_synthesis', 'kokonut_agent_feedback_login'),
    ('agent-commons-liberation-source', 'commons_liberation_synthesis', 'kokonut_agent_commons_liberation_login'),
    ('agent-gnh-alignment-source', 'gnh_alignment_synthesis', 'kokonut_agent_gnh_alignment_login'),
    ('agent-regenerator-source', 'regenerator_synthesis', 'kokonut_agent_regenerator_login'),
    ('agent-capital-efficiency-source', 'capital_efficiency_synthesis', 'kokonut_agent_capital_efficiency_login'),
    ('agent-financial-resilience-source', 'financial_resilience_synthesis', 'kokonut_agent_financial_resilience_login'),
    ('agent-bio-factory-source', 'bio_factory_synthesis', 'kokonut_agent_bio_factory_login'),
    ('agent-open-source-capitalist-source', 'open_source_capitalist_synthesis', 'kokonut_agent_open_source_capitalist_login'),
    ('agent-kokonut-commons-source', 'kokonut_commons_synthesis', 'kokonut_agent_kokonut_commons_login')
ON CONFLICT (principal_key) DO NOTHING;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM (VALUES
              ('agent-summary-deterministic-source', 'ai_summary_synthesis', 'kokonut_agent_summary_deterministic_source_login'),
              ('agent-organic-readiness-source', 'organic_readiness_synthesis', 'kokonut_agent_organic_readiness_login'),
              ('agent-ecological-modeling-source', 'ecological_modeling_synthesis', 'kokonut_agent_ecological_modeling_login'),
              ('agent-holistic-wellbeing-source', 'holistic_wellbeing_synthesis', 'kokonut_agent_holistic_wellbeing_login'),
              ('agent-feedback-source', 'feedback_synthesis', 'kokonut_agent_feedback_login'),
              ('agent-commons-liberation-source', 'commons_liberation_synthesis', 'kokonut_agent_commons_liberation_login'),
              ('agent-gnh-alignment-source', 'gnh_alignment_synthesis', 'kokonut_agent_gnh_alignment_login'),
              ('agent-regenerator-source', 'regenerator_synthesis', 'kokonut_agent_regenerator_login'),
              ('agent-capital-efficiency-source', 'capital_efficiency_synthesis', 'kokonut_agent_capital_efficiency_login'),
              ('agent-financial-resilience-source', 'financial_resilience_synthesis', 'kokonut_agent_financial_resilience_login'),
              ('agent-bio-factory-source', 'bio_factory_synthesis', 'kokonut_agent_bio_factory_login'),
              ('agent-open-source-capitalist-source', 'open_source_capitalist_synthesis', 'kokonut_agent_open_source_capitalist_login'),
              ('agent-kokonut-commons-source', 'kokonut_commons_synthesis', 'kokonut_agent_kokonut_commons_login')
          ) AS expected(principal_key, task_key, login_role)
          LEFT JOIN kokonut_security.ai_summary_worker_task_registry AS registered
            ON registered.principal_key = expected.principal_key
         WHERE registered.principal_key IS NULL
            OR expected.task_key IS DISTINCT FROM registered.task_key
            OR expected.login_role IS DISTINCT FROM registered.login_role
    ) THEN
        RAISE EXCEPTION 'agent worker task registry is missing or conflicts with a required task mapping';
    END IF;
    IF pg_catalog.has_table_privilege(
        'kokonut_agent_task_summary_writer',
        'kokonut_security.ai_summary_worker_task_registry', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'agent task writer can read the task registry directly';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.ai_summary_worker_task_attribution (
    worker_id UUID PRIMARY KEY
        REFERENCES kokonut_security.worker_principal(id) ON DELETE RESTRICT,
    task_key TEXT NOT NULL
        REFERENCES kokonut_security.ai_summary_worker_task_registry(task_key)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    attributed_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

REVOKE ALL ON TABLE kokonut_security.ai_summary_worker_task_attribution FROM PUBLIC;
REVOKE ALL ON TABLE kokonut_security.ai_summary_worker_task_attribution
    FROM kokonut_runtime, directus, kokonut_worker_execution,
         kokonut_agent_task_summary_writer;
GRANT SELECT, INSERT ON TABLE kokonut_security.ai_summary_worker_task_attribution
    TO kokonut_ai_summary_drafter;
GRANT SELECT ON TABLE kokonut_security.ai_summary_worker_task_registry
    TO kokonut_ai_summary_drafter;
GRANT SELECT ON TABLE kokonut_security.ai_summary_worker_task_attribution
    TO kokonut_ai_summary_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.register_current_ai_summary_worker_task()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    authenticated_task_key TEXT;
    authenticated_worker_id UUID;
    registered_task_key TEXT;
BEGIN
    IF pg_catalog.current_setting('role', TRUE)
       IS DISTINCT FROM 'kokonut_agent_task_summary_writer' THEN
        RAISE EXCEPTION 'agent task attribution requires the function-only task writer role'
            USING ERRCODE = '42501';
    END IF;

    SELECT registry.task_key INTO authenticated_task_key
      FROM kokonut_security.ai_summary_worker_task_registry AS registry
     WHERE registry.login_role = SESSION_USER::TEXT;
    IF authenticated_task_key IS NULL THEN
        RAISE EXCEPTION 'agent database login % is not registered for task attribution',
            SESSION_USER
            USING ERRCODE = '42501';
    END IF;

    SELECT scope.actor_id INTO authenticated_worker_id
      FROM kokonut_security.current_worker_scope('ai_summary', 'draft') AS scope
     WHERE scope.actor_id IS NOT NULL
       AND scope.location_id IS NOT NULL;
    IF authenticated_worker_id IS NULL THEN
        RAISE EXCEPTION 'agent task attribution requires signed exact-location draft scope'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO kokonut_security.ai_summary_worker_task_attribution (worker_id, task_key)
    VALUES (authenticated_worker_id, authenticated_task_key)
    ON CONFLICT (worker_id) DO NOTHING;

    SELECT attribution.task_key INTO registered_task_key
      FROM kokonut_security.ai_summary_worker_task_attribution AS attribution
     WHERE attribution.worker_id = authenticated_worker_id;
    IF registered_task_key IS DISTINCT FROM authenticated_task_key THEN
        RAISE EXCEPTION 'agent worker identity is already bound to another task'
            USING ERRCODE = '42501';
    END IF;
    RETURN registered_task_key;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.register_current_ai_summary_worker_task()
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.register_current_ai_summary_worker_task()
    TO kokonut_agent_task_summary_writer;
ALTER FUNCTION kokonut_security.register_current_ai_summary_worker_task()
    OWNER TO kokonut_ai_summary_drafter;

REVOKE ALL ON TABLE kokonut_security.ai_summary_worker_task_registry FROM PUBLIC;
REVOKE ALL ON TABLE kokonut_security.ai_summary_worker_task_registry
    FROM kokonut_runtime, directus, kokonut_worker_execution,
         kokonut_agent_task_summary_writer, kokonut_ai_summary_reviewer;

DO $$
BEGIN
    IF NOT pg_catalog.has_table_privilege(
           'kokonut_ai_summary_reviewer',
           'kokonut_security.ai_summary_worker_task_attribution', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_ai_summary_reviewer',
           'kokonut_security.ai_summary_worker_task_registry', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_runtime',
           'kokonut_security.ai_summary_worker_task_attribution', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'directus',
           'kokonut_security.ai_summary_worker_task_attribution', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_agent_task_summary_writer',
           'kokonut_security.ai_summary_worker_task_attribution', 'SELECT'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_agent_task_summary_writer',
           'kokonut_security.ai_summary_worker_task_registry', 'SELECT'
       ) THEN
        RAISE EXCEPTION 'agent task attribution table grants exceed the function-owner boundary';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.prevent_ai_summary_unregistered_worker_review()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    creator_worker_id UUID;
BEGIN
    IF NEW.decision <> 'approve' THEN
        RETURN NEW;
    END IF;
    SELECT summary.created_by_worker_id
      INTO creator_worker_id
      FROM public.ai_summary AS summary
     WHERE summary.id = NEW.summary_id
       AND summary.subject_type = 'location'
       AND summary.subject_id = NEW.location_id;
    IF creator_worker_id IS NULL THEN
        RETURN NEW;
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM kokonut_security.ai_summary_worker_task_attribution AS attribution
         WHERE attribution.worker_id = creator_worker_id
    ) THEN
        RAISE EXCEPTION 'AI summary worker task identity is not registered for verification'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.prevent_ai_summary_unregistered_worker_review()
    FROM PUBLIC;
GRANT CREATE ON SCHEMA public TO kokonut_ai_summary_reviewer;
ALTER FUNCTION public.prevent_ai_summary_unregistered_worker_review()
    OWNER TO kokonut_ai_summary_reviewer;
REVOKE CREATE ON SCHEMA public FROM kokonut_ai_summary_reviewer;
DROP TRIGGER IF EXISTS trg_ai_summary_registered_worker_review
    ON public.ai_summary_review_decision;
CREATE TRIGGER trg_ai_summary_registered_worker_review
    BEFORE INSERT ON public.ai_summary_review_decision
    FOR EACH ROW EXECUTE FUNCTION public.prevent_ai_summary_unregistered_worker_review();

CREATE OR REPLACE FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_task(
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
    creator_task_key TEXT
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
           review.review_ready
               AND (summary.created_by_worker_id IS NULL OR attribution.task_key IS NOT NULL),
           CASE
               WHEN summary.created_by_worker_id IS NOT NULL
                    AND attribution.task_key IS NULL
               THEN pg_catalog.array_append(review.blocked_reasons,
                                            'worker_task_unregistered'::TEXT)
               ELSE review.blocked_reasons
           END,
           review.source_references,
           CASE
               WHEN summary.created_by_worker_id IS NULL THEN NULL
               ELSE COALESCE(attribution.task_key, 'unregistered_worker')
           END
      FROM kokonut_security.list_location_ai_summary_reviews_with_sources(
               requested_location_id, requested_limit, requested_offset
           ) AS review
      JOIN public.ai_summary AS summary
        ON summary.id = review.summary_id
       AND summary.subject_type = 'location'
       AND summary.subject_id = requested_location_id
      LEFT JOIN kokonut_security.ai_summary_worker_task_attribution AS attribution
        ON attribution.worker_id = summary.created_by_worker_id
     ORDER BY review.created_at ASC, review.summary_id ASC;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_task(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT SELECT (id, created_by_worker_id) ON TABLE public.ai_summary
    TO kokonut_ai_summary_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_sources(
    UUID, INTEGER, INTEGER
) TO kokonut_ai_summary_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_task(
    UUID, INTEGER, INTEGER
) TO kokonut_ai_summary_reviewer;
ALTER FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_task(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_ai_summary_reviewer;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_task(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'directus') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_task(
            UUID, INTEGER, INTEGER
        ) FROM directus;
        REVOKE ALL ON TABLE kokonut_security.ai_summary_worker_task_registry FROM directus;
    END IF;
END;
$$;

COMMENT ON ROLE kokonut_agent_task_summary_writer IS
    'NOLOGIN function-only role for exact registered agent-task draft creation; it has no table, sequence, general worker-execution, or reviewer privileges.';
COMMENT ON TABLE kokonut_security.ai_summary_worker_task_registry IS
    'Closed registry mapping worker principal keys and dedicated PostgreSQL login roles to registered agent task keys.';
COMMENT ON TABLE kokonut_security.ai_summary_worker_task_attribution IS
    'Private, function-maintained binding between a signed worker ID and its authenticated task key; readable only by the draft and human-review function owners.';
COMMENT ON FUNCTION kokonut_security.register_current_ai_summary_worker_task() IS
    'Binds the signed worker ID to the task mapped from its authenticated PostgreSQL session user before a task writer creates a draft.';
COMMENT ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_worker_task(UUID, INTEGER, INTEGER) IS
    'Returns the exact-location human review queue with database-authenticated creator task attribution; unregistered worker drafts are blocked.';

COMMIT;
