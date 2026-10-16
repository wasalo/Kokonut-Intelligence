-- Force RLS on anomaly source/effect/target tables before migration 413 so
-- its bounded function owner policies are exercised by acceptance.
ALTER TABLE public.sensor_alert
    ALTER COLUMN id SET DEFAULT gen_random_uuid();

ALTER TABLE public.ingestion_log
    ADD CONSTRAINT ingestion_log_test_reject_atomicity_hash
    CHECK (payload_hash <> repeat('f', 64));

INSERT INTO public.sensor_reading (
    id, sensor_id, location_id, sensor_type, value,
    reading_date, reading_time, created_at
) VALUES (
    'a0000000-0000-0000-0000-000000000025',
    'a0000000-0000-0000-0000-000000000011',
    'a0000000-0000-0000-0000-000000000001',
    'soil_moisture', 22, CURRENT_DATE, TIME '12:30', NOW()
);

INSERT INTO public.platform_event (
    id, event_type, source_table, source_id, payload
) VALUES (
    'a0000000-0000-0000-0000-000000000036',
    'sensor_reading', 'sensor_reading',
    'a0000000-0000-0000-0000-000000000025',
    '{"location_id":"a0000000-0000-0000-0000-000000000001",'
     '"sensor_device_id":"a0000000-0000-0000-0000-000000000011"}'::jsonb
);

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'platform_event', 'sensor_reading', 'sensor_device', 'sensor_type',
        'alert_rule', 'sensor_anomaly_effect', 'sensor_alert', 'ingestion_log'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', table_name);
    END LOOP;
END;
$$;
