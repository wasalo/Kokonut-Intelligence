-- Minimal anomaly schema layered over worker_tenant_context_disposable.sql.

CREATE TABLE public.sensor_device (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL
);
INSERT INTO public.sensor_device (id, location_id) VALUES
    ('a0000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000002');

CREATE TABLE public.sensor_reading (
    id UUID PRIMARY KEY,
    sensor_id UUID NOT NULL,
    location_id UUID NOT NULL
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
    ('a0000000-0000-0000-0000-000000000031', 'sensor_reading', 'sensor_reading', 'a0000000-0000-0000-0000-000000000021', '{"location_id":"a0000000-0000-0000-0000-000000000001","sensor_id":"a0000000-0000-0000-0000-000000000011","sensor_device_id":"a0000000-0000-0000-0000-000000000011"}'),
    ('a0000000-0000-0000-0000-000000000032', 'sensor_reading', 'sensor_reading', 'a0000000-0000-0000-0000-000000000021', '{"location_id":"a0000000-0000-0000-0000-000000000001","sensor_id":"a0000000-0000-0000-0000-000000000011","sensor_device_id":"a0000000-0000-0000-0000-000000000012"}'),
    ('a0000000-0000-0000-0000-000000000033', 'sensor_reading', 'sensor_reading', 'a0000000-0000-0000-0000-000000000022', '{"location_id":"a0000000-0000-0000-0000-000000000002","sensor_id":"a0000000-0000-0000-0000-000000000012"}'),
    ('a0000000-0000-0000-0000-000000000034', 'sensor_reading', 'sensor_reading', 'a0000000-0000-0000-0000-000000000021', '{"location_id":"a0000000-0000-0000-0000-000000000001","sensor_device_id":"a0000000-0000-0000-0000-000000000011"}'),
    ('a0000000-0000-0000-0000-000000000035', 'sensor_alert', 'sensor_alert', 'a0000000-0000-0000-0000-000000000041', '{"location_id":"a0000000-0000-0000-0000-000000000001"}');

CREATE TABLE public.alert_rule (
    id UUID PRIMARY KEY,
    enabled BOOLEAN NOT NULL
);
INSERT INTO public.alert_rule (id, enabled) VALUES
    ('a0000000-0000-0000-0000-000000000051', TRUE),
    ('a0000000-0000-0000-0000-000000000052', TRUE),
    ('a0000000-0000-0000-0000-000000000053', FALSE),
    ('a0000000-0000-0000-0000-000000000054', TRUE);

CREATE TABLE public.sensor_alert (
    id UUID PRIMARY KEY,
    sensor_device_id UUID NOT NULL,
    alert_rule_id UUID NOT NULL,
    reading_id UUID,
    severity TEXT NOT NULL,
    status TEXT,
    message TEXT NOT NULL,
    reading_value NUMERIC,
    threshold_value NUMERIC,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO public.sensor_alert (
    id, sensor_device_id, alert_rule_id, reading_id, severity, message
) VALUES
    ('a0000000-0000-0000-0000-000000000041', 'a0000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000052', 'a0000000-0000-0000-0000-000000000021', 'warning', 'same location'),
    ('a0000000-0000-0000-0000-000000000042', 'a0000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000052', 'a0000000-0000-0000-0000-000000000022', 'warning', 'other location');

CREATE TABLE public.sensor_anomaly_effect (
    source_reading_id UUID NOT NULL,
    alert_rule_id UUID NOT NULL,
    source_event_id UUID NOT NULL,
    outcome VARCHAR(20) NOT NULL
        CHECK (outcome IN ('no_match', 'cooldown', 'alert_created')),
    sensor_alert_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_reading_id, alert_rule_id),
    UNIQUE (source_event_id, alert_rule_id),
    CHECK ((outcome = 'alert_created' AND sensor_alert_id IS NOT NULL)
        OR (outcome <> 'alert_created' AND sensor_alert_id IS NULL))
);

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

CREATE TABLE public.notification_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_event_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    destination_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE (source_event_id, channel, destination_key)
);
