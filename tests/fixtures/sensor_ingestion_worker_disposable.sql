-- Minimal source-table contract for migration 431 disposable acceptance.
CREATE TABLE public.driver_registry (
    id UUID PRIMARY KEY,
    driver_name TEXT NOT NULL,
    driver_type TEXT NOT NULL,
    module_path TEXT NOT NULL,
    class_name TEXT NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE public.driver_instance (
    id UUID PRIMARY KEY,
    driver_id UUID NOT NULL REFERENCES public.driver_registry(id),
    instance_name TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::JSONB,
    location_id UUID NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    last_status TEXT,
    last_error TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE public.driver_instance_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID NOT NULL REFERENCES public.driver_instance(id),
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'timeout')),
    records_fetched INTEGER NOT NULL DEFAULT 0,
    records_written INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE public.sensor_type (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    unit TEXT,
    min_value NUMERIC,
    max_value NUMERIC
);

CREATE TABLE public.sensor_device (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE,
    sensor_type_id UUID NOT NULL REFERENCES public.sensor_type(id),
    location_id UUID NOT NULL REFERENCES public.location(id),
    plot_id UUID,
    status TEXT NOT NULL DEFAULT 'active',
    protocol TEXT
);

CREATE TABLE public.sensor_reading (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.location(id),
    plot_id UUID,
    sensor_id UUID NOT NULL REFERENCES public.sensor_device(id),
    sensor_type TEXT NOT NULL,
    reading_date DATE NOT NULL,
    reading_time TIME NOT NULL DEFAULT '00:00:00',
    value NUMERIC(12, 4) NOT NULL,
    unit TEXT,
    quality TEXT NOT NULL DEFAULT 'good',
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    source_system TEXT,
    source_id TEXT,
    source_raw JSONB,
    schema_version TEXT,
    UNIQUE (sensor_id, reading_date, reading_time)
);

CREATE TABLE public.ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_id UUID,
    operation TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    rows_affected INTEGER NOT NULL DEFAULT 0,
    processing_time_ms INTEGER NOT NULL DEFAULT 0,
    processor_version TEXT,
    batch_id TEXT,
    validation_status TEXT,
    validation_errors JSONB NOT NULL DEFAULT '[]'::JSONB,
    validation_warnings JSONB NOT NULL DEFAULT '[]'::JSONB,
    dedupe_key TEXT,
    location_id UUID REFERENCES public.location(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE public.platform_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_id UUID NOT NULL,
    payload JSONB NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE public.clickhouse_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key TEXT NOT NULL UNIQUE,
    source_table TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_table TEXT NOT NULL,
    columns JSONB NOT NULL,
    rows JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);
