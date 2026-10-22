-- Bind deterministic AI-summary source reads to the worker's signed location.
-- Shared crop and expense taxonomies remain network catalogs, while every
-- operational relation is filtered to the exact signed location.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_view_owner'
    ) THEN
        RAISE EXCEPTION 'agent summary source view owner from migration 543 is required';
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
GRANT CREATE ON SCHEMA kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner;

GRANT SELECT ON TABLE
    public.crop,
    public.crop_cycle,
    public.expense_category,
    public.expense_event,
    public.farm_registry_record,
    public.harvest_event,
    public.noi_snapshot,
    public.remote_sensing_observation,
    public.sales_event,
    public.sensor_reading,
    public.soil_carbon_measurement,
    public.species_observation,
    public.weather_observation
TO kokonut_agent_summary_source_view_owner;

GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_deterministic_reader;

DO $$
DECLARE
    source_name TEXT;
    source_kind "char";
    scope_predicate TEXT;
    expected_sources TEXT[] := ARRAY[
        'crop',
        'crop_cycle',
        'expense_category',
        'expense_event',
        'farm_registry_record',
        'harvest_event',
        'noi_snapshot',
        'remote_sensing_observation',
        'sales_event',
        'sensor_reading',
        'soil_carbon_measurement',
        'species_observation',
        'weather_observation'
    ];
    wrapper_name TEXT;
BEGIN
    FOREACH source_name IN ARRAY expected_sources LOOP
        SELECT relation.relkind
          INTO source_kind
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = source_name;
        IF source_kind IS DISTINCT FROM 'r'
           AND source_kind IS DISTINCT FROM 'p'
           AND source_kind IS DISTINCT FROM 'v'
           AND source_kind IS DISTINCT FROM 'm' THEN
            RAISE EXCEPTION 'deterministic source % is missing or has an unsupported relation kind',
                source_name;
        END IF;

        IF source_name IN ('crop', 'expense_category') THEN
            scope_predicate := 'TRUE';
        ELSE
            IF NOT EXISTS (
                SELECT 1
                  FROM pg_catalog.pg_attribute AS attribute
                  JOIN pg_catalog.pg_class AS relation
                    ON relation.oid = attribute.attrelid
                  JOIN pg_catalog.pg_namespace AS namespace
                    ON namespace.oid = relation.relnamespace
                 WHERE namespace.nspname = 'public'
                   AND relation.relname = source_name
                   AND attribute.attname = 'location_id'
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            ) THEN
                RAISE EXCEPTION 'location-scoped deterministic source % lacks location_id',
                    source_name;
            END IF;
            scope_predicate := 'source_row.location_id = scope.location_id';
        END IF;

        wrapper_name := source_name;
        EXECUTE pg_catalog.format(
            'CREATE OR REPLACE VIEW kokonut_agent_source.%I '
            'WITH (security_barrier = true) AS '
            'SELECT source_row.* FROM public.%I AS source_row '
            'WHERE EXISTS ( '
            '  SELECT 1 FROM kokonut_security.current_worker_scope(''ai_summary'', ''read'') AS scope '
            '  WHERE %s'
            ')',
            wrapper_name,
            source_name,
            scope_predicate
        );
        EXECUTE pg_catalog.format(
            'ALTER VIEW kokonut_agent_source.%I OWNER TO kokonut_agent_summary_source_view_owner',
            wrapper_name
        );
    END LOOP;
END;
$$;

-- The deterministic reader now sees wrappers only. Clean any stale direct
-- source, private, or write grants before installing the bounded allowlist.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;

GRANT USAGE ON SCHEMA kokonut_security TO kokonut_agent_summary_deterministic_source_login;
GRANT USAGE ON SCHEMA kokonut_agent_source TO kokonut_agent_summary_deterministic_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) TO kokonut_agent_summary_deterministic_source_login;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_deterministic_reader;
GRANT SELECT ON TABLE
    kokonut_agent_source.crop,
    kokonut_agent_source.crop_cycle,
    kokonut_agent_source.expense_category,
    kokonut_agent_source.expense_event,
    kokonut_agent_source.farm_registry_record,
    kokonut_agent_source.harvest_event,
    kokonut_agent_source.noi_snapshot,
    kokonut_agent_source.remote_sensing_observation,
    kokonut_agent_source.sales_event,
    kokonut_agent_source.sensor_reading,
    kokonut_agent_source.soil_carbon_measurement,
    kokonut_agent_source.species_observation,
    kokonut_agent_source.weather_observation
TO kokonut_agent_summary_deterministic_reader;

REVOKE CREATE ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_view_owner,
         kokonut_agent_summary_deterministic_reader,
         kokonut_agent_summary_deterministic_source_login;

DO $$
DECLARE
    unexpected_public_read TEXT;
    missing_wrapper_read TEXT;
BEGIN
    SELECT pg_catalog.string_agg(relation.relname::TEXT, ', ' ORDER BY relation.relname::TEXT)
      INTO unexpected_public_read
      FROM pg_catalog.pg_class AS relation
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'public'
       AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND pg_catalog.has_table_privilege(
           'kokonut_agent_summary_deterministic_reader', relation.oid, 'SELECT'
       )
       AND relation.relname::TEXT <> ALL (ARRAY[
           'geography_columns', 'geometry_columns', 'spatial_ref_sys'
       ]);
    IF unexpected_public_read IS NOT NULL THEN
        RAISE EXCEPTION
            'deterministic summary reader retains direct public relation access: %',
            unexpected_public_read;
    END IF;

    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_deterministic_source_login',
        'kokonut_agent_source.harvest_event', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'deterministic summary source login can bypass its reader role';
    END IF;

    SELECT pg_catalog.string_agg(wrapper.relname::TEXT, ', ' ORDER BY wrapper.relname::TEXT)
      INTO missing_wrapper_read
      FROM pg_catalog.pg_class AS wrapper
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = wrapper.relnamespace
     WHERE namespace.nspname = 'kokonut_agent_source'
       AND wrapper.relname = ANY (ARRAY[
           'crop', 'crop_cycle', 'expense_category', 'expense_event',
           'farm_registry_record', 'harvest_event', 'noi_snapshot',
           'remote_sensing_observation', 'sales_event', 'sensor_reading',
           'soil_carbon_measurement', 'species_observation', 'weather_observation'
       ])
       AND NOT pg_catalog.has_table_privilege(
           'kokonut_agent_summary_deterministic_reader', wrapper.oid, 'SELECT'
       );
    IF missing_wrapper_read IS NOT NULL THEN
        RAISE EXCEPTION 'deterministic summary reader lacks wrapper access: %',
            missing_wrapper_read;
    END IF;
END;
$$;

COMMIT;
