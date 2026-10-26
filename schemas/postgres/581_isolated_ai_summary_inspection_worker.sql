-- Give standalone AI-summary listing/digest inspection a source identity that
-- cannot read the deterministic generator's operational source projections.
-- The digest view returns no summary content, only its SHA-256 and length.

BEGIN;

DO $$
DECLARE
    role_name TEXT;
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
        RAISE EXCEPTION 'summary source roles from migrations 542/547 are required';
    END IF;

    IF pg_catalog.to_regprocedure('public.digest(bytea,text)') IS NULL THEN
        RAISE EXCEPTION 'pgcrypto digest function is required for bounded inspection';
    END IF;

    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_agent_summary_inspection_reader',
        'kokonut_agent_summary_inspection_login'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
        ) THEN
            EXECUTE pg_catalog.format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        ELSIF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = role_name
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'AI-summary inspection role % has unsafe attributes', role_name;
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE (
                 granted_role.rolname IN (
                     'kokonut_agent_summary_inspection_reader',
                     'kokonut_agent_summary_inspection_login'
                 )
                 OR member_role.rolname IN (
                     'kokonut_agent_summary_inspection_reader',
                     'kokonut_agent_summary_inspection_login'
                 )
               )
           AND NOT (
               granted_role.rolname = 'kokonut_agent_summary_inspection_reader'
               AND member_role.rolname = 'kokonut_agent_summary_inspection_login'
               AND membership.admin_option IS FALSE
               AND membership.inherit_option IS FALSE
               AND membership.set_option IS TRUE
           )
    ) THEN
        RAISE EXCEPTION 'AI-summary inspection roles have unexpected memberships';
    END IF;
END;
$$;

GRANT kokonut_agent_summary_inspection_reader
    TO kokonut_agent_summary_inspection_login
    WITH INHERIT FALSE, SET TRUE;

REVOKE ALL ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;
REVOKE CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;

GRANT USAGE ON SCHEMA kokonut_security
    TO kokonut_agent_summary_inspection_login;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO kokonut_agent_summary_inspection_login;
GRANT USAGE ON SCHEMA public, kokonut_security, kokonut_agent_source
    TO kokonut_agent_summary_inspection_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_inspection_reader;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_agent_summary_inspection_reader;

-- The deterministic generator keeps its thirteen source wrappers but loses
-- both inspection surfaces. The inspection worker gets metadata, a bounded
-- preview, and a digest projection that cannot return raw summary content.
CREATE OR REPLACE VIEW kokonut_agent_source.ai_summary_digest
WITH (security_barrier = true) AS
SELECT summary.id,
       summary.subject_id AS location_id,
       summary.summary_type,
       summary.status,
       summary.model_version,
       pg_catalog.encode(
           public.digest(pg_catalog.convert_to(summary.content, 'UTF8'), 'sha256'),
           'hex'
       ) AS content_sha256,
       pg_catalog.char_length(summary.content) AS content_length
  FROM public.ai_summary AS summary
 WHERE summary.subject_type = 'location'
   AND EXISTS (
       SELECT 1
         FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = summary.subject_id
   );

ALTER VIEW kokonut_agent_source.ai_summary_digest
    OWNER TO kokonut_agent_summary_source_view_owner;

REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.ai_summary_list,
    kokonut_agent_source.ai_summary_inspection,
    kokonut_agent_source.ai_summary_digest
FROM PUBLIC,
     kokonut_agent_summary_deterministic_reader,
     kokonut_agent_summary_deterministic_source_login,
     kokonut_agent_summary_inspection_reader,
     kokonut_agent_summary_inspection_login;
REVOKE ALL PRIVILEGES ON TABLE public.ai_summary
    FROM kokonut_agent_summary_inspection_reader,
         kokonut_agent_summary_inspection_login;

GRANT SELECT ON TABLE
    kokonut_agent_source.ai_summary_list,
    kokonut_agent_source.ai_summary_digest
TO kokonut_agent_summary_inspection_reader;

DO $$
DECLARE
    unexpected_relation TEXT;
    missing_relation TEXT;
    unexpected_public_relation TEXT;
BEGIN
    SELECT pg_catalog.string_agg(relation.relname::TEXT, ', ' ORDER BY relation.relname::TEXT)
      INTO unexpected_relation
      FROM pg_catalog.pg_class AS relation
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'kokonut_agent_source'
       AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND pg_catalog.has_table_privilege(
           'kokonut_agent_summary_inspection_reader', relation.oid, 'SELECT'
       )
       AND relation.relname::TEXT <> ALL (
           ARRAY['ai_summary_list', 'ai_summary_digest']::TEXT[]
       );
    IF unexpected_relation IS NOT NULL THEN
        RAISE EXCEPTION 'AI-summary inspection reader can select unapproved projections: %',
            unexpected_relation;
    END IF;

    SELECT pg_catalog.string_agg(expected.name, ', ' ORDER BY expected.name)
      INTO missing_relation
      FROM unnest(ARRAY['ai_summary_list', 'ai_summary_digest']::TEXT[])
           AS expected(name)
     WHERE NOT pg_catalog.has_table_privilege(
         'kokonut_agent_summary_inspection_reader',
         pg_catalog.format('kokonut_agent_source.%I', expected.name), 'SELECT'
     );
    IF missing_relation IS NOT NULL THEN
        RAISE EXCEPTION 'AI-summary inspection reader lacks projections: %',
            missing_relation;
    END IF;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_deterministic_reader',
        'kokonut_agent_source.ai_summary_list', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_deterministic_reader',
        'kokonut_agent_source.ai_summary_inspection', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_deterministic_reader',
        'kokonut_agent_source.ai_summary_digest', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'deterministic source reader retains AI-summary inspection access';
    END IF;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_inspection_reader',
        'kokonut_agent_source.ai_summary_inspection', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_inspection_login',
        'kokonut_agent_source.ai_summary_list', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_inspection_login',
        'kokonut_agent_source.ai_summary_digest', 'SELECT'
    ) OR pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_inspection_login', 'kokonut_agent_source', 'USAGE'
    ) THEN
        RAISE EXCEPTION 'AI-summary inspection login bypasses its SET-only reader';
    END IF;

    SELECT pg_catalog.string_agg(relation.relname::TEXT, ', ' ORDER BY relation.relname::TEXT)
      INTO unexpected_public_relation
      FROM pg_catalog.pg_class AS relation
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'public'
       AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND pg_catalog.has_table_privilege(
           'kokonut_agent_summary_inspection_reader', relation.oid, 'SELECT'
       )
       AND relation.relname::TEXT <> ALL (ARRAY[
           'geography_columns', 'geometry_columns', 'spatial_ref_sys'
       ]::TEXT[]);
    IF unexpected_public_relation IS NOT NULL THEN
        RAISE EXCEPTION 'AI-summary inspection reader can select public relations: %',
            unexpected_public_relation;
    END IF;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_inspection_reader', 'public.ai_summary', 'INSERT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_inspection_reader',
        'kokonut_agent_source.ai_summary_digest', 'UPDATE'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_inspection_login',
        'kokonut_agent_source.ai_summary_digest', 'SELECT'
    ) OR NOT pg_catalog.has_function_privilege(
        'kokonut_agent_summary_inspection_login',
        'kokonut_security.set_worker_tenant_context(text,uuid,text,text)', 'EXECUTE'
    ) OR NOT pg_catalog.has_function_privilege(
        'kokonut_agent_summary_inspection_reader',
        'public.digest(bytea,text)', 'EXECUTE'
    ) OR pg_catalog.has_function_privilege(
        'kokonut_agent_summary_inspection_login',
        'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'AI-summary inspection reader or login exceeds its contract';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc AS proc
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(
                  proc.proacl,
                  pg_catalog.acldefault('f', proc.proowner)
              )
          ) AS function_acl
          JOIN pg_catalog.pg_roles AS grantee
            ON grantee.oid = function_acl.grantee
         WHERE proc.oid = 'public.digest(bytea,text)'::pg_catalog.regprocedure
           AND grantee.rolname = 'kokonut_agent_summary_inspection_login'
           AND function_acl.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'AI-summary inspection login has a direct digest function grant';
    END IF;
END;
$$;

COMMENT ON VIEW kokonut_agent_source.ai_summary_digest IS
    'Exact-location signed AI-summary digest metadata; summary content is never exposed.';

COMMIT;
