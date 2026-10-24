CREATE TABLE public.location (
    id UUID PRIMARY KEY
);
INSERT INTO public.location (id) VALUES
    ('a0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000002');

CREATE TABLE public.sensor_device (
    id UUID PRIMARY KEY,
    location_id UUID
);
INSERT INTO public.sensor_device (id, location_id) VALUES
    ('a0000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002');

CREATE TABLE public.sensor_reading (
    id UUID PRIMARY KEY,
    sensor_id TEXT NOT NULL,
    location_id UUID
);
INSERT INTO public.sensor_reading (id, sensor_id, location_id) VALUES
    ('a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002');

CREATE TABLE public.platform_event (
    id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    source_table TEXT,
    source_id UUID,
    payload JSONB NOT NULL DEFAULT '{}'
);
INSERT INTO public.platform_event (id, event_type, source_table, source_id, payload) VALUES
    ('a0000000-0000-0000-0000-000000000031', 'sensor_reading', 'sensor_reading', 'a0000000-0000-0000-0000-000000000021', '{"location_id":"a0000000-0000-0000-0000-000000000001","sensor_id":"a0000000-0000-0000-0000-000000000011"}'),
    ('a0000000-0000-0000-0000-000000000032', 'sensor_reading', 'sensor_reading', 'a0000000-0000-0000-0000-000000000022', '{"location_id":"a0000000-0000-0000-0000-000000000001","sensor_id":"a0000000-0000-0000-0000-000000000012"}'),
    ('a0000000-0000-0000-0000-000000000033', 'sensor_reading', 'other_table', 'a0000000-0000-0000-0000-000000000022', '{"location_id":"a0000000-0000-0000-0000-000000000002","sensor_id":"a0000000-0000-0000-0000-000000000012"}'),
    ('a0000000-0000-0000-0000-000000000034', 'sensor_alert', 'sensor_alert', 'a0000000-0000-0000-0000-000000000041', '{"alert_id":"a0000000-0000-0000-0000-000000000041","location_id":"a0000000-0000-0000-0000-000000000001"}'),
    ('a0000000-0000-0000-0000-000000000035', 'sensor_alert', 'sensor_alert', 'a0000000-0000-0000-0000-000000000042', '{"alert_id":"a0000000-0000-0000-0000-000000000042","location_id":"not-a-uuid"}'),
    ('a0000000-0000-0000-0000-000000000036', 'sensor_reading', 'sensor_reading', 'a0000000-0000-0000-0000-000000000021', '{"location_id":"a0000000-0000-0000-0000-000000000001","sensor_id":"a0000000-0000-0000-0000-000000000011","sensor_device_id":"a0000000-0000-0000-0000-000000000012"}');

CREATE TABLE public.sensor_alert (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sensor_device_id UUID NOT NULL,
    alert_rule_id UUID NOT NULL,
    reading_id UUID,
    severity TEXT NOT NULL,
    status TEXT,
    message TEXT NOT NULL,
    reading_value NUMERIC,
    threshold_value NUMERIC,
    triggered_at TIMESTAMPTZ
);
INSERT INTO public.sensor_alert
    (id, sensor_device_id, alert_rule_id, reading_id, severity, message) VALUES
    ('a0000000-0000-0000-0000-000000000041', 'a0000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000051', 'a0000000-0000-0000-0000-000000000021', 'warning', 'matched'),
    ('a0000000-0000-0000-0000-000000000042', 'a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000052', 'a0000000-0000-0000-0000-000000000021', 'warning', 'mismatched'),
    ('a0000000-0000-0000-0000-000000000043', 'a0000000-0000-0000-0000-000000000099', 'a0000000-0000-0000-0000-000000000053', NULL, 'warning', 'missing device'),
    ('a0000000-0000-0000-0000-000000000044', 'a0000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000053', NULL, 'warning', 'missing source reading');

CREATE TABLE public.sensor_anomaly_effect (
    source_reading_id UUID NOT NULL,
    alert_rule_id UUID NOT NULL,
    source_event_id UUID NOT NULL,
    outcome TEXT NOT NULL,
    PRIMARY KEY (source_reading_id, alert_rule_id)
);
INSERT INTO public.sensor_anomaly_effect
    (source_reading_id, alert_rule_id, source_event_id, outcome) VALUES
    ('a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000051', 'a0000000-0000-0000-0000-000000000031', 'no_match'),
    ('a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000052', 'a0000000-0000-0000-0000-000000000032', 'no_match'),
    ('a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000053', 'a0000000-0000-0000-0000-000000000033', 'no_match'),
    ('a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000054', 'a0000000-0000-0000-0000-000000000036', 'no_match');

CREATE TABLE public.ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system TEXT NOT NULL,
    source_table TEXT,
    source_id TEXT,
    target_table TEXT NOT NULL,
    target_id UUID,
    operation TEXT,
    payload_hash TEXT,
    status TEXT,
    error_message TEXT,
    rows_affected INTEGER,
    processing_time_ms INTEGER,
    processor_version TEXT,
    batch_id TEXT,
    validation_status TEXT,
    validation_errors JSONB,
    validation_warnings JSONB,
    dedupe_key TEXT
);
INSERT INTO public.ingestion_log
    (id, source_system, source_table, source_id, target_table, target_id) VALUES
    ('a0000000-0000-0000-0000-000000000061', 'anomaly_detector', 'sensor_reading', 'a0000000-0000-0000-0000-000000000021', 'sensor_alert', 'a0000000-0000-0000-0000-000000000041'),
    ('a0000000-0000-0000-0000-000000000062', 'anomaly_detector', 'sensor_reading', 'missing-reading', 'sensor_alert', 'a0000000-0000-0000-0000-000000000041'),
    ('a0000000-0000-0000-0000-000000000063', 'anomaly_detector', 'sensor_reading', 'a0000000-0000-0000-0000-000000000022', 'sensor_alert', 'a0000000-0000-0000-0000-000000000042');

CREATE TABLE public.notification_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_event_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    destination_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE (source_event_id, channel, destination_key)
);
INSERT INTO public.notification_outbox
    (source_event_id, event_type, channel, destination_key, payload) VALUES
    ('a0000000-0000-0000-0000-000000000034', 'sensor_alert', 'webhook', 'primary', '{"subject":"Synthetic alert"}'),
    ('a0000000-0000-0000-0000-000000000035', 'sensor_alert', 'webhook', 'primary', '{"subject":"Unresolved alert"}');
