CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kokonut_operator_auth NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kokonut_worker_execution NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT;

CREATE TABLE public.platform_event (
    id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::JSONB
);
CREATE TABLE public.notification_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_event_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    channel VARCHAR(30) NOT NULL
        CHECK (channel IN ('webhook', 'directus', 'email')),
    destination_key VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    location_id UUID,
    UNIQUE (source_event_id, channel, destination_key)
);

INSERT INTO public.platform_event (id, event_type, payload) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'threshold_breached',
     '{"location_id":"b0000000-0000-0000-0000-000000000001"}'),
    ('a0000000-0000-0000-0000-000000000002', 'data_stale', '{}'),
    ('a0000000-0000-0000-0000-000000000003', 'other_event', '{}'),
    ('a0000000-0000-0000-0000-000000000004', 'threshold_breached',
     '{"location_id":"b0000000-0000-0000-0000-000000000001"}'),
    ('a0000000-0000-0000-0000-000000000005', 'threshold_breached',
     '{"location_id":"b0000000-0000-0000-0000-000000000001"}'),
    ('a0000000-0000-0000-0000-000000000006', 'threshold_breached',
     '{"location_id":"b0000000-0000-0000-0000-000000000001"}'),
    ('a0000000-0000-0000-0000-000000000007', 'threshold_breached',
     '{"location_id":"b0000000-0000-0000-0000-000000000001"}');

ALTER TABLE public.platform_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_event FORCE ROW LEVEL SECURITY;
ALTER TABLE public.notification_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_outbox FORCE ROW LEVEL SECURITY;
