-- Bind shared-agent synthesis source reads to the exact signed worker
-- location. The source login can no longer select the unfiltered public
-- views directly; its wrapper views require an active ai_summary/read context.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_view_owner'
    ) THEN
        CREATE ROLE kokonut_agent_summary_source_view_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_view_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'agent summary source view owner has unsafe role attributes';
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

CREATE SCHEMA IF NOT EXISTS kokonut_agent_source;
REVOKE ALL ON SCHEMA kokonut_agent_source FROM PUBLIC;
REVOKE ALL ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;
GRANT USAGE ON SCHEMA kokonut_agent_source
    TO kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_view_owner;
GRANT CREATE ON SCHEMA kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_agent_summary_source_view_owner;

GRANT SELECT ON TABLE
    public.v_public_adaptive_stewardship_summary,
    public.v_public_adoption_barrier_assessment,
    public.v_public_algorithmic_redistribution_mechanism,
    public.v_public_anti_capture_governance_policy,
    public.v_public_bio_factory_batch_summary,
    public.v_public_bio_factory_quality_test_summary,
    public.v_public_bio_input_provenance_summary,
    public.v_public_bio_recipe_library_summary,
    public.v_public_bio_regional_input_summary,
    public.v_public_capital_alignment_summary,
    public.v_public_capital_efficiency_summary,
    public.v_public_capital_provider_utility_summary,
    public.v_public_commons_redistribution_policy,
    public.v_public_community_governance_mechanism,
    public.v_public_cultural_context_summary,
    public.v_public_cultural_preservation_summary,
    public.v_public_farm_launch_unit_economics,
    public.v_public_federation_protocol,
    public.v_public_financial_sustainability_summary,
    public.v_public_foundational_wellbeing_summary,
    public.v_public_gnh_alignment_summary,
    public.v_public_governance_inclusion_summary,
    public.v_public_governance_throughput_summary,
    public.v_public_green_paper_publication_status,
    public.v_public_land_stewardship_summary,
    public.v_public_network_scaling_target,
    public.v_public_open_source_impact_artifact,
    public.v_public_participatory_governance_summary,
    public.v_public_participatory_signal_experiment,
    public.v_public_perpetual_value_stress_test,
    public.v_public_regenerative_efficiency_summary,
    public.v_public_regenerative_outcome_summary,
    public.v_public_renewable_energy_summary,
    public.v_public_replication_readiness_summary,
    public.v_public_risk_mitigation_summary,
    public.v_public_scaling_roadmap_summary,
    public.v_public_stakeholder_feedback_summary,
    public.v_public_time_liberation_summary,
    public.v_public_vulnerable_access_summary,
    public.v_public_wellbeing_metric_summary
TO kokonut_agent_summary_source_view_owner;

GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_source_reader;
DO $$
DECLARE
    source_entry RECORD;
    predicate_sql TEXT;
    expected_views TEXT[] := ARRAY[
        'v_public_adaptive_stewardship_summary',
        'v_public_adoption_barrier_assessment',
        'v_public_algorithmic_redistribution_mechanism',
        'v_public_anti_capture_governance_policy',
        'v_public_bio_factory_batch_summary',
        'v_public_bio_factory_quality_test_summary',
        'v_public_bio_input_provenance_summary',
        'v_public_bio_recipe_library_summary',
        'v_public_bio_regional_input_summary',
        'v_public_capital_alignment_summary',
        'v_public_capital_efficiency_summary',
        'v_public_capital_provider_utility_summary',
        'v_public_commons_redistribution_policy',
        'v_public_community_governance_mechanism',
        'v_public_cultural_context_summary',
        'v_public_cultural_preservation_summary',
        'v_public_farm_launch_unit_economics',
        'v_public_federation_protocol',
        'v_public_financial_sustainability_summary',
        'v_public_foundational_wellbeing_summary',
        'v_public_gnh_alignment_summary',
        'v_public_governance_inclusion_summary',
        'v_public_governance_throughput_summary',
        'v_public_green_paper_publication_status',
        'v_public_land_stewardship_summary',
        'v_public_network_scaling_target',
        'v_public_open_source_impact_artifact',
        'v_public_participatory_governance_summary',
        'v_public_participatory_signal_experiment',
        'v_public_perpetual_value_stress_test',
        'v_public_regenerative_efficiency_summary',
        'v_public_regenerative_outcome_summary',
        'v_public_renewable_energy_summary',
        'v_public_replication_readiness_summary',
        'v_public_risk_mitigation_summary',
        'v_public_scaling_roadmap_summary',
        'v_public_stakeholder_feedback_summary',
        'v_public_time_liberation_summary',
        'v_public_vulnerable_access_summary',
        'v_public_wellbeing_metric_summary'
    ];
    actual_views TEXT[];
    missing_location_column TEXT;
    relation_kind "char";
BEGIN
    SELECT pg_catalog.array_agg(source_view_name ORDER BY source_view_name)
      INTO actual_views
      FROM kokonut_security.ai_summary_source_reference_view;
    IF actual_views IS DISTINCT FROM expected_views THEN
        RAISE EXCEPTION 'synthesis source-view registry differs from the reviewed 40-view allowlist';
    END IF;

    FOR source_entry IN
        SELECT source_view_name, source_scope
          FROM kokonut_security.ai_summary_source_reference_view
         ORDER BY source_view_name
    LOOP
        SELECT relation.relkind
          INTO relation_kind
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = source_entry.source_view_name;
        IF relation_kind IS DISTINCT FROM 'v' THEN
            RAISE EXCEPTION 'registered synthesis source % is not a public view',
                source_entry.source_view_name;
        END IF;

        IF source_entry.source_scope <> 'network'
           AND NOT EXISTS (
               SELECT 1
                 FROM pg_catalog.pg_attribute AS attribute
                 JOIN pg_catalog.pg_class AS relation
                   ON relation.oid = attribute.attrelid
                 JOIN pg_catalog.pg_namespace AS namespace
                   ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'public'
                  AND relation.relname = source_entry.source_view_name
                  AND attribute.attname = 'location_id'
                  AND attribute.attnum > 0
                  AND NOT attribute.attisdropped
           ) THEN
            missing_location_column := source_entry.source_view_name;
            RAISE EXCEPTION 'scoped synthesis source % lacks location_id',
                missing_location_column;
        END IF;

        predicate_sql := CASE source_entry.source_scope
            WHEN 'location' THEN
                'source_row.location_id = scope.location_id'
            WHEN 'location_or_network' THEN
                '(source_row.location_id = scope.location_id OR source_row.location_id IS NULL)'
            WHEN 'network' THEN
                'TRUE'
            ELSE NULL
        END;
        IF predicate_sql IS NULL THEN
            RAISE EXCEPTION 'unsupported synthesis source scope for %',
                source_entry.source_view_name;
        END IF;

        EXECUTE pg_catalog.format(
            'CREATE OR REPLACE VIEW kokonut_agent_source.%I '
            'WITH (security_barrier = true) AS '
            'SELECT source_row.* FROM public.%I AS source_row '
            'WHERE EXISTS ( '
            '  SELECT 1 FROM kokonut_security.current_worker_scope('
            '''ai_summary'', ''read'') AS scope '
            '  WHERE %s'
            ')',
            source_entry.source_view_name,
            source_entry.source_view_name,
            predicate_sql
        );
        EXECUTE pg_catalog.format(
            'ALTER VIEW kokonut_agent_source.%I OWNER TO kokonut_agent_summary_source_view_owner',
            source_entry.source_view_name
        );
    END LOOP;
END;
$$;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_source_login,
         kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_source_login,
         kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_source_login,
         kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_view_owner;
GRANT USAGE ON SCHEMA kokonut_security
    TO kokonut_agent_summary_source_login;
GRANT USAGE ON SCHEMA kokonut_security
    TO kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_view_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO kokonut_agent_summary_source_login;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_view_owner;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA kokonut_agent_source
    TO kokonut_agent_summary_source_reader;
REVOKE CREATE ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_view_owner,
         kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;

DO $$
DECLARE
    unfiltered_source_access TEXT;
    missing_scoped_access TEXT;
BEGIN
    SELECT pg_catalog.string_agg(source_view_name, ', ' ORDER BY source_view_name)
      INTO unfiltered_source_access
      FROM kokonut_security.ai_summary_source_reference_view
     WHERE pg_catalog.has_table_privilege(
               'kokonut_agent_summary_source_reader',
               pg_catalog.format('public.%I', source_view_name), 'SELECT'
           )
        OR pg_catalog.has_table_privilege(
               'kokonut_agent_summary_source_login',
               pg_catalog.format('public.%I', source_view_name), 'SELECT'
           );
    IF unfiltered_source_access IS NOT NULL THEN
        RAISE EXCEPTION 'synthesis source login can bypass scoped views: %',
            unfiltered_source_access;
    END IF;

    SELECT pg_catalog.string_agg(source_view_name, ', ' ORDER BY source_view_name)
      INTO missing_scoped_access
      FROM kokonut_security.ai_summary_source_reference_view
     WHERE NOT pg_catalog.has_table_privilege(
               'kokonut_agent_summary_source_reader',
               pg_catalog.format('kokonut_agent_source.%I', source_view_name),
               'SELECT'
           );
    IF missing_scoped_access IS NOT NULL THEN
        RAISE EXCEPTION 'synthesis source reader is missing scoped views: %',
            missing_scoped_access;
    END IF;
END;
$$;

-- This connection authenticates with its own login, and is deliberately not a
-- member of kokonut_worker_execution. It can only request its own exact
-- ai_summary/read worker grant before switching into the filtered reader role.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE member_role.rolname = 'kokonut_agent_summary_source_login'
           AND granted_role.rolname = 'kokonut_worker_execution'
    ) THEN
        RAISE EXCEPTION 'synthesis source login must not inherit worker execution';
    END IF;
END;
$$;

COMMENT ON SCHEMA kokonut_agent_source IS
    'Location-scoped security-barrier views for the isolated synthesis source reader; queries require signed ai_summary/read worker context.';
COMMENT ON FUNCTION kokonut_security.set_worker_tenant_context(TEXT, UUID, TEXT, TEXT) IS
    'Validates a worker credential, exact grant, active location, organization, and current owner under row locks, then signs transaction-bound system_worker context; the synthesis source login is granted only this function and a filtered reader role.';

COMMIT;
