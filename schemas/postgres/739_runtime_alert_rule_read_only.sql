-- Keep alert rules readable to the application while moving lazy default
-- creation behind one fixed, owner-controlled function.  The function does
-- not initialize during migration: pilot seed 003 must retain its existing
-- eight-rule behavior before this optional lazy initialization is invoked.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_alert_rule_owner'
    ) THEN
        CREATE ROLE kokonut_alert_rule_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_alert_rule_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_alert_rule_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_alert_rule_owner'
            OR member_role.rolname = 'kokonut_alert_rule_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_alert_rule_owner must not have role memberships';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
         WHERE relation.relowner = (
             SELECT oid FROM pg_catalog.pg_roles
              WHERE rolname = 'kokonut_alert_rule_owner'
         )
           AND relation.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
    ) THEN
        RAISE EXCEPTION 'kokonut_alert_rule_owner must not own database relations';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = 'alert_rule'
           AND relation.relrowsecurity
    ) THEN
        RAISE EXCEPTION 'alert_rule unexpectedly has RLS; review global catalog semantics';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_alert_rule_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_alert_rule_owner;
GRANT SELECT ON TABLE public.sensor_type, public.alert_rule
    TO kokonut_alert_rule_owner;
GRANT INSERT ON TABLE public.alert_rule TO kokonut_alert_rule_owner;

CREATE OR REPLACE FUNCTION kokonut_security.ensure_default_alert_rules()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    inserted_count integer;
BEGIN
    -- The empty-catalog test and insert must serialize with concurrent callers.
    PERFORM pg_catalog.pg_advisory_xact_lock(1935765537, 739);

    IF EXISTS (SELECT 1 FROM public.alert_rule LIMIT 1) THEN
        RETURN 0;
    END IF;

    INSERT INTO public.alert_rule (
        name,
        sensor_type_id,
        metric,
        operator,
        threshold_value,
        severity,
        enabled,
        auto_create_claim,
        claim_type
    )
    SELECT defaults.name,
           sensor_type.id,
           defaults.metric,
           defaults.operator,
           defaults.threshold_value,
           defaults.severity,
           true,
           defaults.auto_create_claim,
           defaults.claim_type
      FROM (VALUES
          ('Soil Moisture Low', 'soil_moisture', 'value', 'lt', 15.0, 'warning', false, NULL),
          ('Soil Moisture Critical', 'soil_moisture', 'value', 'lt', 8.0, 'critical', true, 'sensor_anomaly'),
          ('Soil Moisture High', 'soil_moisture', 'value', 'gt', 85.0, 'warning', false, NULL),
          ('Air Temperature High', 'air_temperature', 'value', 'gt', 40.0, 'warning', false, NULL),
          ('Air Temperature Critical High', 'air_temperature', 'value', 'gt', 45.0, 'critical', true, 'sensor_anomaly'),
          ('Air Temperature Low', 'air_temperature', 'value', 'lt', 5.0, 'warning', false, NULL),
          ('Humidity High', 'humidity', 'value', 'gt', 90.0, 'warning', false, NULL),
          ('Rainfall Heavy', 'rainfall', 'value', 'gt', 50.0, 'warning', false, NULL),
          ('Soil Moisture Rapid Drop', 'soil_moisture', 'rate_of_change', 'lt', -5.0, 'warning', false, NULL),
          ('Temperature Rapid Rise', 'air_temperature', 'rate_of_change', 'gt', 10.0, 'warning', false, NULL)
      ) AS defaults(
          name, sensor_type_name, metric, operator, threshold_value,
          severity, auto_create_claim, claim_type
      )
      JOIN public.sensor_type AS sensor_type
        ON sensor_type.name = defaults.sensor_type_name;

    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    RETURN inserted_count;
END;
$$;

ALTER FUNCTION kokonut_security.ensure_default_alert_rules()
    OWNER TO kokonut_alert_rule_owner;
REVOKE ALL ON FUNCTION kokonut_security.ensure_default_alert_rules()
    FROM PUBLIC;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_alert_rule_owner;

REVOKE ALL PRIVILEGES ON TABLE public.alert_rule FROM PUBLIC;
DO $$
DECLARE
    role_name text;
    column_name text;
    sequence_row record;
    relation_oid regclass := 'public.alert_rule'::regclass;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.ensure_default_alert_rules()
            TO kokonut_runtime;
    END IF;

    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.alert_rule FROM %I', role_name
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = relation_oid
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.alert_rule FROM %2$I',
                    column_name, role_name
                );
            END LOOP;
            FOR sequence_row IN
                SELECT sequence_namespace.nspname, sequence.relname
                  FROM pg_catalog.pg_depend AS dependency
                  JOIN pg_catalog.pg_class AS sequence
                    ON sequence.oid = dependency.objid
                   AND sequence.relkind = 'S'
                  JOIN pg_catalog.pg_namespace AS sequence_namespace
                    ON sequence_namespace.oid = sequence.relnamespace
                 WHERE dependency.refobjid = relation_oid
                   AND dependency.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
                   AND dependency.classid = 'pg_catalog.pg_class'::pg_catalog.regclass
                   AND dependency.deptype IN ('a', 'i')
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE ALL PRIVILEGES ON SEQUENCE %I.%I FROM %I',
                    sequence_row.nspname, sequence_row.relname, role_name
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'GRANT SELECT ON TABLE public.alert_rule TO %I', role_name
            );
        END IF;
    END LOOP;

    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = relation_oid
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
            'ON TABLE public.alert_rule FROM PUBLIC', column_name
        );
    END LOOP;
    FOR sequence_row IN
        SELECT sequence_namespace.nspname, sequence.relname
          FROM pg_catalog.pg_depend AS dependency
          JOIN pg_catalog.pg_class AS sequence
            ON sequence.oid = dependency.objid AND sequence.relkind = 'S'
          JOIN pg_catalog.pg_namespace AS sequence_namespace
            ON sequence_namespace.oid = sequence.relnamespace
         WHERE dependency.refobjid = relation_oid
           AND dependency.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
           AND dependency.classid = 'pg_catalog.pg_class'::pg_catalog.regclass
           AND dependency.deptype IN ('a', 'i')
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ALL PRIVILEGES ON SEQUENCE %I.%I FROM PUBLIC',
            sequence_row.nspname, sequence_row.relname
        );
    END LOOP;
END;
$$;

COMMENT ON TABLE public.alert_rule IS
    'Global sensor-rule catalog. Runtime and optional Directus identities retain read-only access; lazy default rows are inserted through kokonut_security.ensure_default_alert_rules(), and curated seeds remain owner-controlled. This shared configuration relation is not tenant scoped and retains its existing RLS-disabled model.';

INSERT INTO kokonut_security.directus_relation_privilege_policy
    (schema_name, relation_name, access_mode, source_migration)
VALUES
    ('public', 'alert_rule', 'read_only', '739_runtime_alert_rule_read_only.sql')
ON CONFLICT (schema_name, relation_name) DO UPDATE
   SET access_mode = EXCLUDED.access_mode,
       source_migration = EXCLUDED.source_migration;

COMMIT;
