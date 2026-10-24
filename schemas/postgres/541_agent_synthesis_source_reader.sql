-- Give registered synthesis agents a read-only database identity that can
-- select only the public views approved by the source-reference registry and
-- the public PostGIS metadata catalogs inherited from PUBLIC.
-- Application queries still enforce exact location/network scope; this role
-- is relation-level isolation, not tenant RLS.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_reader'
    ) THEN
        CREATE ROLE kokonut_agent_summary_source_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'agent synthesis source-reader role has unsafe attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_login'
    ) THEN
        CREATE ROLE kokonut_agent_summary_source_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_login'
           AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'agent synthesis source login has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE (member_role.rolname = 'kokonut_agent_summary_source_login'
                AND (granted_role.rolname <> 'kokonut_agent_summary_source_reader'
                     OR membership.admin_option OR membership.inherit_option
                     OR NOT membership.set_option))
            OR granted_role.rolname = 'kokonut_agent_summary_source_login'
            OR (member_role.rolname = 'kokonut_agent_summary_source_reader'
                AND granted_role.rolname <> 'kokonut_agent_summary_source_login')
            OR (granted_role.rolname = 'kokonut_agent_summary_source_reader'
                AND member_role.rolname <> 'kokonut_agent_summary_source_login')
    ) THEN
        RAISE EXCEPTION 'agent synthesis source roles have unexpected memberships';
    END IF;
END;
$$;

GRANT kokonut_agent_summary_source_reader TO kokonut_agent_summary_source_login
    WITH INHERIT FALSE, SET TRUE;
GRANT USAGE ON SCHEMA public TO kokonut_agent_summary_source_reader;
REVOKE CREATE ON SCHEMA public
    FROM kokonut_agent_summary_source_reader;

-- This role is dedicated to this allowlist. Revoke any stale table grants
-- before installing the explicit view-only contract, including on replay.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_summary_source_reader;

-- A replay may encounter a source login that predates this exact boundary.
-- Remove any direct application grants from that login as well; it only needs
-- the bounded context setter in kokonut_security before SET ROLE to the reader.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_summary_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_summary_source_login;
REVOKE CREATE ON SCHEMA public
    FROM kokonut_agent_summary_source_login;

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
    TO kokonut_agent_summary_source_reader;

-- pg_stat_statements contains instance-wide query telemetry, including query
-- text. Its extension default grants SELECT to PUBLIC, which would make that
-- telemetry visible to this reader and every other database role. Keep the
-- stats views private; a monitoring consumer must receive a separate reviewed
-- grant instead of inheriting access through PUBLIC.
DO $$
DECLARE
    relation_name TEXT;
    relation_oid OID;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'pg_stat_statements',
        'pg_stat_statements_info'
    ] LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', relation_name)
        );
        IF relation_oid IS NOT NULL THEN
            EXECUTE pg_catalog.format(
                'REVOKE SELECT ON TABLE %s FROM PUBLIC',
                relation_oid::regclass
            );
        END IF;
    END LOOP;
END;
$$;

DO $$
DECLARE
    unapproved_relation TEXT;
    approved_relations TEXT[] := ARRAY[
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
        'v_public_wellbeing_metric_summary',
        'geography_columns',
        'geometry_columns',
        'spatial_ref_sys'
    ];
BEGIN
    SELECT pg_catalog.string_agg(rel.relname::text, ', ' ORDER BY rel.relname::text)
      INTO unapproved_relation
      FROM pg_catalog.pg_class AS rel
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = rel.relnamespace
     WHERE namespace.nspname = 'public'
       AND rel.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND pg_catalog.has_table_privilege(
           'kokonut_agent_summary_source_reader', rel.oid, 'SELECT'
       )
       AND rel.relname::text <> ALL (approved_relations);
    IF unapproved_relation IS NOT NULL THEN
        RAISE EXCEPTION
            'agent synthesis source reader can select unapproved public relations: %',
            unapproved_relation;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND (
               pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_source_reader', relation.oid, 'INSERT'
               )
               OR pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_source_reader', relation.oid, 'UPDATE'
               )
               OR pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_source_reader', relation.oid, 'DELETE'
               )
               OR pg_catalog.has_table_privilege(
                   'kokonut_agent_summary_source_reader', relation.oid, 'TRUNCATE'
               )
           )
    ) THEN
        RAISE EXCEPTION 'agent synthesis source reader has public write privileges';
    END IF;

    IF pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_source_reader', 'public', 'CREATE'
    ) THEN
        RAISE EXCEPTION 'agent synthesis source reader can create public objects';
    END IF;
END;
$$;

COMMIT;
