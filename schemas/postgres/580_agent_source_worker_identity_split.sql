-- Give each non-synthesis agent source task a separate worker identity and
-- read-only role. The shared synthesis identity retains only its registered
-- synthesis views; EBF, CIDS, and Delphi can read only their own projections.

BEGIN;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_agent_ebf_source_reader',
        'kokonut_agent_ebf_source_login',
        'kokonut_agent_cids_source_reader',
        'kokonut_agent_cids_source_login',
        'kokonut_agent_delphi_source_reader',
        'kokonut_agent_delphi_source_login'
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
            RAISE EXCEPTION 'agent source role % has unsafe attributes', role_name;
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE (
                 granted_role.rolname IN (
                     'kokonut_agent_ebf_source_reader', 'kokonut_agent_ebf_source_login',
                     'kokonut_agent_cids_source_reader', 'kokonut_agent_cids_source_login',
                     'kokonut_agent_delphi_source_reader', 'kokonut_agent_delphi_source_login'
                 )
                 OR member_role.rolname IN (
                     'kokonut_agent_ebf_source_reader', 'kokonut_agent_ebf_source_login',
                     'kokonut_agent_cids_source_reader', 'kokonut_agent_cids_source_login',
                     'kokonut_agent_delphi_source_reader', 'kokonut_agent_delphi_source_login'
                 )
               )
           AND NOT (
               (granted_role.rolname = 'kokonut_agent_ebf_source_reader'
                AND member_role.rolname = 'kokonut_agent_ebf_source_login'
                AND membership.admin_option IS FALSE
                AND membership.inherit_option IS FALSE
                AND membership.set_option IS TRUE)
               OR
               (granted_role.rolname = 'kokonut_agent_cids_source_reader'
                AND member_role.rolname = 'kokonut_agent_cids_source_login'
                AND membership.admin_option IS FALSE
                AND membership.inherit_option IS FALSE
                AND membership.set_option IS TRUE)
               OR
               (granted_role.rolname = 'kokonut_agent_delphi_source_reader'
                AND member_role.rolname = 'kokonut_agent_delphi_source_login'
                AND membership.admin_option IS FALSE
                AND membership.inherit_option IS FALSE
                AND membership.set_option IS TRUE)
           )
    ) THEN
        RAISE EXCEPTION 'task-specific agent source roles have unexpected memberships';
    END IF;
END;
$$;

GRANT kokonut_agent_ebf_source_reader TO kokonut_agent_ebf_source_login
    WITH INHERIT FALSE, SET TRUE;
GRANT kokonut_agent_cids_source_reader TO kokonut_agent_cids_source_login
    WITH INHERIT FALSE, SET TRUE;
GRANT kokonut_agent_delphi_source_reader TO kokonut_agent_delphi_source_login
    WITH INHERIT FALSE, SET TRUE;

GRANT USAGE ON SCHEMA kokonut_security TO
    kokonut_agent_ebf_source_login,
    kokonut_agent_cids_source_login,
    kokonut_agent_delphi_source_login;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO
    kokonut_agent_ebf_source_login,
    kokonut_agent_cids_source_login,
    kokonut_agent_delphi_source_login;

GRANT USAGE ON SCHEMA kokonut_security, kokonut_agent_source TO
    kokonut_agent_ebf_source_reader,
    kokonut_agent_cids_source_reader,
    kokonut_agent_delphi_source_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT) TO
    kokonut_agent_ebf_source_reader,
    kokonut_agent_cids_source_reader,
    kokonut_agent_delphi_source_reader;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_security
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_security
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;
REVOKE CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
    FROM kokonut_agent_ebf_source_reader,
         kokonut_agent_ebf_source_login,
         kokonut_agent_cids_source_reader,
         kokonut_agent_cids_source_login,
         kokonut_agent_delphi_source_reader,
         kokonut_agent_delphi_source_login;

GRANT USAGE ON SCHEMA kokonut_security TO
    kokonut_agent_ebf_source_login,
    kokonut_agent_cids_source_login,
    kokonut_agent_delphi_source_login;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO
    kokonut_agent_ebf_source_login,
    kokonut_agent_cids_source_login,
    kokonut_agent_delphi_source_login;
GRANT USAGE ON SCHEMA kokonut_security, kokonut_agent_source TO
    kokonut_agent_ebf_source_reader,
    kokonut_agent_cids_source_reader,
    kokonut_agent_delphi_source_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT) TO
    kokonut_agent_ebf_source_reader,
    kokonut_agent_cids_source_reader,
    kokonut_agent_delphi_source_reader;

-- Remove these capability-specific projections from the shared summary reader.
REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.v_ebf_evidence_gap_summary,
    kokonut_agent_source.cids_location,
    kokonut_agent_source.cids_stakeholder_outcome,
    kokonut_agent_source.cids_farm_impact_mapping,
    kokonut_agent_source.cids_metric_value,
    kokonut_agent_source.cids_stakeholder_feedback,
    kokonut_agent_source.cids_impact_claim,
    kokonut_agent_source.delphi_live_summary
FROM PUBLIC,
     kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;

GRANT SELECT ON TABLE kokonut_agent_source.v_ebf_evidence_gap_summary
    TO kokonut_agent_ebf_source_reader;
GRANT SELECT ON TABLE
    kokonut_agent_source.cids_location,
    kokonut_agent_source.cids_stakeholder_outcome,
    kokonut_agent_source.cids_farm_impact_mapping,
    kokonut_agent_source.cids_metric_value,
    kokonut_agent_source.cids_stakeholder_feedback,
    kokonut_agent_source.cids_impact_claim
TO kokonut_agent_cids_source_reader;
GRANT SELECT ON TABLE kokonut_agent_source.delphi_live_summary
    TO kokonut_agent_delphi_source_reader;

DO $$
DECLARE
    role_pair RECORD;
    unexpected_view_access TEXT;
BEGIN
    FOR role_pair IN
        SELECT * FROM (VALUES
            ('kokonut_agent_ebf_source_reader', 'kokonut_agent_ebf_source_login',
             ARRAY['v_ebf_evidence_gap_summary']::TEXT[]),
            ('kokonut_agent_cids_source_reader', 'kokonut_agent_cids_source_login',
             ARRAY['cids_location', 'cids_stakeholder_outcome',
                   'cids_farm_impact_mapping', 'cids_metric_value',
                   'cids_stakeholder_feedback', 'cids_impact_claim']::TEXT[]),
            ('kokonut_agent_delphi_source_reader', 'kokonut_agent_delphi_source_login',
             ARRAY['delphi_live_summary']::TEXT[])
        ) AS pair(reader_role, login_role, allowed_views)
    LOOP
        SELECT pg_catalog.string_agg(relation.relname, ', ' ORDER BY relation.relname)
          INTO unexpected_view_access
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'kokonut_agent_source'
           AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND pg_catalog.has_table_privilege(role_pair.reader_role, relation.oid, 'SELECT')
           AND relation.relname::TEXT <> ALL (role_pair.allowed_views);
        IF unexpected_view_access IS NOT NULL THEN
            RAISE EXCEPTION '% can select unapproved source views: %',
                role_pair.reader_role, unexpected_view_access;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'public'
               AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
               AND pg_catalog.has_table_privilege(
                   role_pair.reader_role, relation.oid, 'SELECT'
               )
               AND relation.relname::TEXT <> ALL (ARRAY[
                   'geography_columns', 'geometry_columns', 'spatial_ref_sys'
               ]::TEXT[])
        ) THEN
            RAISE EXCEPTION '% can read public relations directly',
                role_pair.reader_role;
        END IF;

        IF pg_catalog.has_schema_privilege(role_pair.login_role, 'kokonut_agent_source', 'USAGE')
           OR pg_catalog.has_table_privilege(
               role_pair.login_role,
               pg_catalog.format('kokonut_agent_source.%I', role_pair.allowed_views[1]),
               'SELECT'
           ) THEN
            RAISE EXCEPTION '% bypasses its SET-only source-reader role',
                role_pair.login_role;
        END IF;
    END LOOP;
END;
$$;

COMMENT ON ROLE kokonut_agent_ebf_source_reader IS
    'Read-only access to the consent-safe EBF evidence-gap projection under ebf_scorecard/read context.';
COMMENT ON ROLE kokonut_agent_cids_source_reader IS
    'Read-only access to the six migration-approved CIDS projections under cids_export/read context.';
COMMENT ON ROLE kokonut_agent_delphi_source_reader IS
    'Read-only access to the consent-aware Delphi aggregate projection under delphi/read context.';

COMMIT;
