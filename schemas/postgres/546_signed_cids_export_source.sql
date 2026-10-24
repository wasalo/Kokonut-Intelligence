-- Expose only the CIDS Essential Tier projection through an exact-location
-- signed worker scope. The agent uses a dedicated read-only login and does
-- not inherit the shared application database identity.

BEGIN;

DO $$
DECLARE
    required_relation TEXT;
    source_kind "char";
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

    FOREACH required_relation IN ARRAY ARRAY[
        'public.location', 'public.farm', 'public.farm_registry_record',
        'public.stakeholder_outcome', 'public.farm_impact_mapping',
        'public.sdg', 'public.metric_definition', 'public.metric_value',
        'public.stakeholder_feedback', 'public.impact_claim',
        'public.evidence_maturity_level'
    ] LOOP
        SELECT relation.relkind
          INTO source_kind
          FROM pg_catalog.pg_class AS relation
         WHERE relation.oid = pg_catalog.to_regclass(required_relation);
        IF source_kind IS DISTINCT FROM 'r' AND source_kind IS DISTINCT FROM 'p' THEN
            RAISE EXCEPTION 'CIDS source relation % is required', required_relation;
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_agent_summary_source_view_owner'
            OR member_role.rolname = 'kokonut_agent_summary_source_view_owner'
    ) THEN
        RAISE EXCEPTION 'agent source view owner must have no role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security, kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_login;
GRANT CREATE ON SCHEMA kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_source_reader;

GRANT SELECT ON TABLE
    public.location,
    public.farm,
    public.farm_registry_record,
    public.stakeholder_outcome,
    public.farm_impact_mapping,
    public.sdg,
    public.metric_definition,
    public.metric_value,
    public.stakeholder_feedback,
    public.impact_claim,
    public.evidence_maturity_level
TO kokonut_agent_summary_source_view_owner;

-- These policies are dormant when a source table has RLS disabled. If a
-- deployment enables or forces RLS, the shared non-login view owner sees only
-- exact locations authorized for either existing ai_summary/read wrappers or
-- the new cids_export/read projection.
DROP POLICY IF EXISTS cids_agent_source_read ON public.location;
CREATE POLICY cids_agent_source_read ON public.location
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                 WHERE id = scope.location_id)
        OR EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE id = scope.location_id)
    );

DROP POLICY IF EXISTS cids_agent_source_read ON public.farm;
CREATE POLICY cids_agent_source_read ON public.farm
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                 WHERE farm.location_id = scope.location_id)
        OR EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE farm.location_id = scope.location_id)
    );
DROP POLICY IF EXISTS cids_agent_source_read ON public.farm_registry_record;
CREATE POLICY cids_agent_source_read ON public.farm_registry_record
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                 WHERE farm_registry_record.location_id = scope.location_id)
        OR EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE farm_registry_record.location_id = scope.location_id)
    );
DROP POLICY IF EXISTS cids_agent_source_read ON public.stakeholder_outcome;
CREATE POLICY cids_agent_source_read ON public.stakeholder_outcome
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                 WHERE stakeholder_outcome.location_id = scope.location_id)
        OR EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE stakeholder_outcome.location_id = scope.location_id)
    );
DROP POLICY IF EXISTS cids_agent_source_read ON public.farm_impact_mapping;
CREATE POLICY cids_agent_source_read ON public.farm_impact_mapping
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                 WHERE farm_impact_mapping.location_id = scope.location_id)
        OR EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE farm_impact_mapping.location_id = scope.location_id)
    );
DROP POLICY IF EXISTS cids_agent_source_read ON public.metric_value;
CREATE POLICY cids_agent_source_read ON public.metric_value
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                 WHERE metric_value.location_id = scope.location_id)
        OR EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE metric_value.location_id = scope.location_id)
    );
DROP POLICY IF EXISTS cids_agent_source_read ON public.stakeholder_feedback;
CREATE POLICY cids_agent_source_read ON public.stakeholder_feedback
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        is_public IS TRUE
        AND consent_given IS TRUE
        AND consent_scope IN ('public_summary', 'public_quote', 'public_full')
        AND status = 'published'
        AND NULLIF(TRIM(COALESCE(public_summary, '')), '') IS NOT NULL
        AND (
            EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                     WHERE stakeholder_feedback.location_id = scope.location_id)
            OR EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                        WHERE stakeholder_feedback.location_id = scope.location_id)
        )
    );
DROP POLICY IF EXISTS cids_agent_source_read ON public.impact_claim;
CREATE POLICY cids_agent_source_read ON public.impact_claim
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                 WHERE impact_claim.location_id = scope.location_id)
        OR EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE impact_claim.location_id = scope.location_id)
    );

DROP POLICY IF EXISTS cids_agent_source_read ON public.sdg;
CREATE POLICY cids_agent_source_read ON public.sdg
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (
            SELECT 1
              FROM public.farm_impact_mapping AS mapping
              JOIN kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                ON scope.location_id = mapping.location_id
             WHERE mapping.sdg_number = sdg.sdg_number
        )
        OR EXISTS (
            SELECT 1
              FROM public.farm_impact_mapping AS mapping
              JOIN kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                ON scope.location_id = mapping.location_id
             WHERE mapping.sdg_number = sdg.sdg_number
        )
    );
DROP POLICY IF EXISTS cids_agent_source_read ON public.metric_definition;
CREATE POLICY cids_agent_source_read ON public.metric_definition
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (
            SELECT 1
              FROM public.metric_value AS value
              JOIN kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                ON scope.location_id = value.location_id
             WHERE value.metric_id = metric_definition.id
        )
        OR EXISTS (
            SELECT 1
              FROM public.metric_value AS value
              JOIN kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                ON scope.location_id = value.location_id
             WHERE value.metric_id = metric_definition.id
        )
    );
DROP POLICY IF EXISTS cids_agent_source_read ON public.evidence_maturity_level;
CREATE POLICY cids_agent_source_read ON public.evidence_maturity_level
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (
            SELECT 1
              FROM public.impact_claim AS claim
              JOIN kokonut_security.current_worker_scope('cids_export', 'read') AS scope
                ON scope.location_id = claim.location_id
             WHERE claim.evidence_maturity = evidence_maturity_level.level
        )
        OR EXISTS (
            SELECT 1
              FROM public.impact_claim AS claim
              JOIN kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                ON scope.location_id = claim.location_id
             WHERE claim.evidence_maturity = evidence_maturity_level.level
        )
    );

CREATE OR REPLACE VIEW kokonut_agent_source.cids_location
WITH (security_barrier = true) AS
SELECT location.id,
       location.name,
       location.slug,
       location.description,
       farm.name AS farm_name,
       farm.description AS farm_description,
       registry.project_summary,
       registry.local_problem,
       registry.proposed_solution
  FROM public.location AS location
  LEFT JOIN LATERAL (
      SELECT source_farm.name, source_farm.description
        FROM public.farm AS source_farm
       WHERE source_farm.location_id = location.id
       ORDER BY source_farm.id
       LIMIT 1
  ) AS farm ON TRUE
  LEFT JOIN LATERAL (
      SELECT source_registry.project_summary,
             source_registry.local_problem,
             source_registry.proposed_solution
        FROM public.farm_registry_record AS source_registry
       WHERE source_registry.location_id = location.id
       ORDER BY source_registry.created_at DESC NULLS LAST,
                source_registry.id DESC
       LIMIT 1
  ) AS registry ON TRUE
 WHERE EXISTS (
     SELECT 1
       FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
      WHERE location.id = scope.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.cids_stakeholder_outcome
WITH (security_barrier = true) AS
SELECT outcome.id,
       outcome.location_id,
       outcome.status,
       outcome.created_at,
       outcome.outcome_name,
       outcome.outcome_description,
       outcome.stakeholder_group,
       outcome.importance,
       outcome.is_underserved,
       outcome.importance_perspective,
       outcome.sdg_number
  FROM public.stakeholder_outcome AS outcome
 WHERE EXISTS (
     SELECT 1
       FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
      WHERE outcome.location_id = scope.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.cids_farm_impact_mapping
WITH (security_barrier = true) AS
SELECT mapping.id,
       mapping.location_id,
       mapping.status,
       mapping.framework_key,
       mapping.dimension_key,
       mapping.sdg_number,
       sdg.name AS sdg_name
  FROM public.farm_impact_mapping AS mapping
  LEFT JOIN public.sdg AS sdg ON sdg.sdg_number = mapping.sdg_number
 WHERE EXISTS (
     SELECT 1
       FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
      WHERE mapping.location_id = scope.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.cids_metric_value
WITH (security_barrier = true) AS
SELECT metric_value.location_id,
       definition.metric_key,
       definition.display_name,
       definition.description,
       definition.unit,
       metric_value.id AS metric_value_id,
       metric_value.period_start,
       metric_value.period_end,
       metric_value.value,
       metric_value.unit AS value_unit,
       metric_value.verified,
       definition.active,
       metric_value.computation_method,
       metric_value.computed_at
  FROM public.metric_value AS metric_value
  JOIN public.metric_definition AS definition
    ON definition.id = metric_value.metric_id
 WHERE EXISTS (
     SELECT 1
       FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
      WHERE metric_value.location_id = scope.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.cids_stakeholder_feedback
WITH (security_barrier = true) AS
SELECT feedback.id,
       feedback.location_id,
       feedback.feedback_date,
       feedback.stakeholder_group
  FROM public.stakeholder_feedback AS feedback
 WHERE feedback.is_public IS TRUE
   AND feedback.consent_given IS TRUE
   AND feedback.consent_scope IN ('public_summary', 'public_quote', 'public_full')
   AND feedback.status = 'published'
   AND NULLIF(TRIM(COALESCE(feedback.public_summary, '')), '') IS NOT NULL
   AND EXISTS (
       SELECT 1
         FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
        WHERE feedback.location_id = scope.location_id
   );

CREATE OR REPLACE VIEW kokonut_agent_source.cids_impact_claim
WITH (security_barrier = true) AS
SELECT claim.id,
       claim.location_id,
       claim.status,
       claim.claim_date,
       claim.claim_text,
       claim.period_start,
       claim.period_end,
       claim.confidence_notes,
       claim.evidence_maturity,
       maturity.label AS evidence_maturity_label,
       claim.methodology_ref,
       claim.external_verifier,
       claim.attestation_uid
  FROM public.impact_claim AS claim
  LEFT JOIN public.evidence_maturity_level AS maturity
    ON maturity.level = claim.evidence_maturity
 WHERE EXISTS (
     SELECT 1
       FROM kokonut_security.current_worker_scope('cids_export', 'read') AS scope
      WHERE claim.location_id = scope.location_id
 );

ALTER VIEW kokonut_agent_source.cids_location
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.cids_stakeholder_outcome
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.cids_farm_impact_mapping
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.cids_metric_value
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.cids_stakeholder_feedback
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.cids_impact_claim
    OWNER TO kokonut_agent_summary_source_view_owner;

REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.cids_location,
    kokonut_agent_source.cids_stakeholder_outcome,
    kokonut_agent_source.cids_farm_impact_mapping,
    kokonut_agent_source.cids_metric_value,
    kokonut_agent_source.cids_stakeholder_feedback,
    kokonut_agent_source.cids_impact_claim
FROM PUBLIC,
     kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;
GRANT SELECT ON TABLE
    kokonut_agent_source.cids_location,
    kokonut_agent_source.cids_stakeholder_outcome,
    kokonut_agent_source.cids_farm_impact_mapping,
    kokonut_agent_source.cids_metric_value,
    kokonut_agent_source.cids_stakeholder_feedback,
    kokonut_agent_source.cids_impact_claim
TO kokonut_agent_summary_source_reader;

REVOKE ALL PRIVILEGES ON TABLE
    public.location,
    public.farm,
    public.farm_registry_record,
    public.stakeholder_outcome,
    public.farm_impact_mapping,
    public.sdg,
    public.metric_definition,
    public.metric_value,
    public.stakeholder_feedback,
    public.impact_claim,
    public.evidence_maturity_level
FROM kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;
REVOKE ALL ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_login;
REVOKE CREATE ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_view_owner,
         kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;

DO $$
DECLARE
    wrapper_name TEXT;
    source_relation TEXT;
BEGIN
    FOREACH wrapper_name IN ARRAY ARRAY[
        'cids_location', 'cids_stakeholder_outcome',
        'cids_farm_impact_mapping', 'cids_metric_value',
        'cids_stakeholder_feedback', 'cids_impact_claim'
    ] LOOP
        IF NOT pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_reader',
            pg_catalog.format('kokonut_agent_source.%I', wrapper_name), 'SELECT'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_login',
            pg_catalog.format('kokonut_agent_source.%I', wrapper_name), 'SELECT'
        ) THEN
            RAISE EXCEPTION 'CIDS source-reader grant boundary is invalid for %', wrapper_name;
        END IF;
        IF pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_reader',
            pg_catalog.format('kokonut_agent_source.%I', wrapper_name), 'INSERT'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_reader',
            pg_catalog.format('kokonut_agent_source.%I', wrapper_name), 'UPDATE'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_reader',
            pg_catalog.format('kokonut_agent_source.%I', wrapper_name), 'DELETE'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_reader',
            pg_catalog.format('kokonut_agent_source.%I', wrapper_name), 'TRUNCATE'
        ) THEN
            RAISE EXCEPTION 'CIDS source reader has write privileges on %', wrapper_name;
        END IF;
    END LOOP;

    FOREACH source_relation IN ARRAY ARRAY[
        'location', 'farm', 'farm_registry_record', 'stakeholder_outcome',
        'farm_impact_mapping', 'sdg', 'metric_definition', 'metric_value',
        'stakeholder_feedback', 'impact_claim', 'evidence_maturity_level'
    ] LOOP
        IF pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_reader',
            pg_catalog.format('public.%I', source_relation), 'SELECT'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_login',
            pg_catalog.format('public.%I', source_relation), 'SELECT'
        ) THEN
            RAISE EXCEPTION 'CIDS source identities can read raw relation %', source_relation;
        END IF;
    END LOOP;

    IF pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_source_login', 'kokonut_agent_source', 'USAGE'
    ) THEN
        RAISE EXCEPTION 'CIDS source login can bypass the NOLOGIN reader role';
    END IF;
END;
$$;

COMMENT ON VIEW kokonut_agent_source.cids_location IS
    'Minimal location, farm, and registry labels for the signed CIDS Essential Tier export.';
COMMENT ON VIEW kokonut_agent_source.cids_stakeholder_feedback IS
    'Stakeholder group only; source rows must be published, public, consented, and include a nonblank public summary.';
COMMIT;
