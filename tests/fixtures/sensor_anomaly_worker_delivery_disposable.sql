-- Force row policies for the complete event-driven anomaly transaction before
-- migration 414 installs the no-login function-owner policies.
DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'platform_event', 'sensor_anomaly_effect', 'sensor_alert',
        'sensor_reading', 'sensor_device', 'sensor_type', 'alert_rule',
        'location', 'mrv_claim', 'notification_outbox', 'actuation_log'
    ] LOOP
        IF to_regclass(format('public.%I', table_name)) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
            EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', table_name);
        END IF;
    END LOOP;
END;
$$;

UPDATE public.alert_rule
   SET auto_create_claim = TRUE,
       claim_type = 'sensor_anomaly',
       actuator_enabled = TRUE,
       actuator_type = 'irrigation',
       actuator_command = 'open_valve',
       human_approval_required = TRUE
 WHERE id = 'a0000000-0000-0000-0000-000000000091';

UPDATE public.alert_rule
   SET enabled = FALSE
 WHERE id <> 'a0000000-0000-0000-0000-000000000091';

INSERT INTO public.sensor_reading (
    id, sensor_id, location_id, sensor_type, value,
    reading_date, reading_time, created_at
) VALUES (
    'a0000000-0000-0000-0000-000000000026',
    'a0000000-0000-0000-0000-000000000011',
    'a0000000-0000-0000-0000-000000000001',
    'soil_moisture', 18, CURRENT_DATE, TIME '12:45', NOW()
);

INSERT INTO public.platform_event (
    id, event_type, source_table, source_id, payload
) VALUES (
    'a0000000-0000-0000-0000-000000000037',
    'sensor_reading', 'sensor_reading',
    'a0000000-0000-0000-0000-000000000026',
    '{"location_id":"a0000000-0000-0000-0000-000000000001",'
     '"sensor_id":"a0000000-0000-0000-0000-000000000011",'
     '"sensor_device_id":"a0000000-0000-0000-0000-000000000011"}'::jsonb
);
