-- Bound standalone AI-summary listing and digest inspection to the
-- database-signed exact location read grant.

BEGIN;

DO $$
DECLARE
    relation_kind "char";
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_view_owner'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_deterministic_reader'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_deterministic_source_login'
    ) THEN
        RAISE EXCEPTION 'deterministic source-reader roles from migration 544 are required';
    END IF;

    SELECT relation.relkind
      INTO relation_kind
      FROM pg_catalog.pg_class AS relation
     WHERE relation.oid = pg_catalog.to_regclass('public.ai_summary');
    IF relation_kind IS DISTINCT FROM 'r' AND relation_kind IS DISTINCT FROM 'p' THEN
        RAISE EXCEPTION 'AI-summary inspection requires public.ai_summary as a table';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_agent_summary_source_view_owner'
            OR member_role.rolname = 'kokonut_agent_summary_source_view_owner'
    ) THEN
        RAISE EXCEPTION 'agent summary source view owner must have no role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security, kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_deterministic_reader,
       kokonut_agent_summary_deterministic_source_login;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_deterministic_reader;
GRANT SELECT ON TABLE public.ai_summary
    TO kokonut_agent_summary_source_view_owner;

DROP POLICY IF EXISTS agent_summary_inspection_source_read ON public.ai_summary;
CREATE POLICY agent_summary_inspection_source_read ON public.ai_summary
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        subject_type = 'location'
        AND EXISTS (
            SELECT 1
              FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
             WHERE scope.location_id = ai_summary.subject_id
        )
    );

CREATE OR REPLACE VIEW kokonut_agent_source.ai_summary_list
WITH (security_barrier = true) AS
SELECT summary.id,
       summary.subject_id AS location_id,
       summary.summary_type,
       summary.status,
       summary.created_at,
       LEFT(summary.content, 80) AS preview
  FROM public.ai_summary AS summary
 WHERE summary.subject_type = 'location'
   AND EXISTS (
       SELECT 1
         FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = summary.subject_id
   );

CREATE OR REPLACE VIEW kokonut_agent_source.ai_summary_inspection
WITH (security_barrier = true) AS
SELECT summary.id,
       summary.subject_id AS location_id,
       summary.summary_type,
       summary.status,
       summary.created_at,
       summary.model_version,
       summary.content
  FROM public.ai_summary AS summary
 WHERE summary.subject_type = 'location'
   AND EXISTS (
       SELECT 1
         FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = summary.subject_id
   );

ALTER VIEW kokonut_agent_source.ai_summary_list
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.ai_summary_inspection
    OWNER TO kokonut_agent_summary_source_view_owner;

REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.ai_summary_list,
    kokonut_agent_source.ai_summary_inspection
FROM PUBLIC,
     kokonut_agent_summary_deterministic_reader,
     kokonut_agent_summary_deterministic_source_login;
GRANT SELECT ON TABLE
    kokonut_agent_source.ai_summary_list,
    kokonut_agent_source.ai_summary_inspection
TO kokonut_agent_summary_deterministic_reader;

REVOKE ALL PRIVILEGES ON TABLE public.ai_summary
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.ai_summary_list,
    kokonut_agent_source.ai_summary_inspection
    FROM kokonut_agent_summary_deterministic_source_login;
REVOKE ALL ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_deterministic_source_login;
REVOKE CREATE ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_view_owner,
         kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;

DO $$
DECLARE
    view_name TEXT;
BEGIN
    FOREACH view_name IN ARRAY ARRAY[
        'ai_summary_list', 'ai_summary_inspection'
    ] LOOP
        IF NOT pg_catalog.has_table_privilege(
            'kokonut_agent_summary_deterministic_reader',
            pg_catalog.format('kokonut_agent_source.%I', view_name), 'SELECT'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_deterministic_source_login',
            pg_catalog.format('kokonut_agent_source.%I', view_name), 'SELECT'
        ) THEN
            RAISE EXCEPTION 'AI-summary inspection grants are invalid for %', view_name;
        END IF;
        IF pg_catalog.has_table_privilege(
            'kokonut_agent_summary_deterministic_reader',
            pg_catalog.format('kokonut_agent_source.%I', view_name), 'INSERT'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_deterministic_reader',
            pg_catalog.format('kokonut_agent_source.%I', view_name), 'UPDATE'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_deterministic_reader',
            pg_catalog.format('kokonut_agent_source.%I', view_name), 'DELETE'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_deterministic_reader',
            pg_catalog.format('kokonut_agent_source.%I', view_name), 'TRUNCATE'
        ) THEN
            RAISE EXCEPTION 'AI-summary inspection reader has write access to %', view_name;
        END IF;
    END LOOP;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_deterministic_reader', 'public.ai_summary', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_deterministic_source_login', 'public.ai_summary', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'AI-summary inspection identities retain raw table access';
    END IF;
    IF pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_deterministic_source_login',
        'kokonut_agent_source', 'USAGE'
    ) THEN
        RAISE EXCEPTION 'AI-summary source login can bypass the NOLOGIN reader';
    END IF;
    IF NOT pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_deterministic_reader',
        'kokonut_agent_source', 'USAGE'
    ) OR NOT pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_source_view_owner',
        'kokonut_agent_source', 'USAGE'
    ) THEN
        RAISE EXCEPTION 'AI-summary inspection views are inaccessible to their reader or owner';
    END IF;
END;
$$;

COMMENT ON VIEW kokonut_agent_source.ai_summary_list IS
    'Exact-location signed AI-summary metadata and 80-character previews.';
COMMENT ON VIEW kokonut_agent_source.ai_summary_inspection IS
    'Exact-location signed AI-summary content for read-only digest inspection.';

COMMIT;
