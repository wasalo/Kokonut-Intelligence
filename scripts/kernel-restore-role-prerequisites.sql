-- Apply as a PostgreSQL superuser before restoring a DB-only Kernel archive.
-- pg_dump archives RLS policies but intentionally omits cluster-global roles;
-- these disabled placeholders let pg_restore recreate policies and function
-- ownership without enabling any application or worker login.
BEGIN;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_anomaly_actuation_owner',
        'kokonut_anomaly_alert_owner',
        'kokonut_anomaly_claim_owner',
        'kokonut_anomaly_effect_owner',
        'kokonut_anomaly_event_owner',
        'kokonut_anomaly_notification_owner',
        'kokonut_anomaly_read_owner',
        'kokonut_cache_invalidation_owner',
        'kokonut_climate_owner',
        'kokonut_eas_indexer_login',
        'kokonut_eas_indexer_owner',
        'kokonut_farm_activity_event_owner',
        'kokonut_financial_projection_owner',
        'kokonut_gateway_context_owner',
        'kokonut_market_data_login',
        'kokonut_market_data_owner',
        'kokonut_mobile_context_owner',
        'kokonut_mobile_credential_owner',
        'kokonut_mobile_device_revoke_owner',
        'kokonut_noi_snapshot_owner',
        'kokonut_notification_enqueue_login',
        'kokonut_notification_enqueue_owner',
        'kokonut_operator_auth',
        'kokonut_operator_auth_owner',
        'kokonut_operator_context_owner',
        'kokonut_remote_sensing_login',
        'kokonut_remote_sensing_owner',
        'kokonut_runtime',
        'kokonut_sensor_ingestion_login',
        'kokonut_sensor_ingestion_owner',
        'kokonut_weather_forecast_owner',
        'kokonut_weather_observation_owner',
        'kokonut_worker_context_owner',
        'kokonut_worker_execution',
        'kokonut_worker_login'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        ELSIF EXISTS (
            SELECT 1 FROM pg_roles
             WHERE rolname = role_name
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'security role % has unsafe role attributes', role_name;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_auth_members AS membership
              JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
              JOIN pg_roles AS member_role ON member_role.oid = membership.member
             WHERE granted_role.rolname = role_name OR member_role.rolname = role_name
        ) THEN
            RAISE EXCEPTION 'security role % has role membership', role_name;
        END IF;
    END LOOP;
END;
$$;

COMMIT;
