-- Bind EBF evidence-gap reads to the exact signed scorecard location grant.
-- The shared agent source login can invoke only bounded context setup and
-- switch to its NOLOGIN reader; the wrapper does not broaden other source
-- views, which remain gated by ai_summary/read.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_view_owner'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_reader'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_login'
    ) THEN
        RAISE EXCEPTION 'agent source-reader roles from migration 543 are required';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = 'v_ebf_evidence_gap_summary'
           AND relation.relkind = 'v'
    ) THEN
        RAISE EXCEPTION 'public.v_ebf_evidence_gap_summary must be a view';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_attribute AS attribute
          JOIN pg_catalog.pg_class AS relation
            ON relation.oid = attribute.attrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = 'v_ebf_evidence_gap_summary'
           AND attribute.attname = 'location_id'
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    ) THEN
        RAISE EXCEPTION 'EBF evidence-gap source must expose location_id';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_login;
GRANT USAGE ON SCHEMA kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_source_reader;
REVOKE ALL ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_login;
GRANT SELECT ON TABLE public.v_ebf_evidence_gap_summary
    TO kokonut_agent_summary_source_view_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_source_reader;

CREATE OR REPLACE VIEW kokonut_agent_source.v_ebf_evidence_gap_summary
WITH (security_barrier = true) AS
SELECT source_row.scorecard_id,
       source_row.location_id,
       source_row.pillar_key,
       source_row.pillar_name,
       source_row.normalized_score,
       source_row.confidence_level,
       source_row.evidence_maturity_level,
       source_row.evidence_maturity_label,
       source_row.evidence_count,
       source_row.public_safe_evidence_count,
       source_row.gap_status
  FROM public.v_ebf_evidence_gap_summary AS source_row
 WHERE EXISTS (
     SELECT 1
       FROM kokonut_security.current_worker_scope('ebf_scorecard', 'read') AS scope
      WHERE source_row.location_id = scope.location_id
 );

ALTER VIEW kokonut_agent_source.v_ebf_evidence_gap_summary
    OWNER TO kokonut_agent_summary_source_view_owner;

REVOKE ALL PRIVILEGES ON TABLE kokonut_agent_source.v_ebf_evidence_gap_summary
    FROM PUBLIC,
         kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;
GRANT SELECT ON TABLE kokonut_agent_source.v_ebf_evidence_gap_summary
    TO kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON TABLE public.v_ebf_evidence_gap_summary
    FROM kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;
REVOKE CREATE ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;

DO $$
BEGIN
    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.v_ebf_evidence_gap_summary', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_login',
        'public.v_ebf_evidence_gap_summary', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'EBF source identities can bypass the location wrapper';
    END IF;

    IF NOT pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'kokonut_agent_source.v_ebf_evidence_gap_summary', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'agent source reader lacks the signed EBF wrapper';
    END IF;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_login',
        'kokonut_agent_source.v_ebf_evidence_gap_summary', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'EBF source login bypasses its NOLOGIN reader role';
    END IF;

    IF pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_source_login', 'kokonut_agent_source', 'USAGE'
    ) THEN
        RAISE EXCEPTION 'EBF source login can inspect the wrapper schema without its reader role';
    END IF;
END;
$$;

COMMIT;
