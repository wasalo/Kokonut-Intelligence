-- Synthetic table contract needed to replay migration 432 in isolation.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE public.farm (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id),
    name TEXT NOT NULL
);
CREATE TABLE public.plot (
    id UUID PRIMARY KEY,
    farm_id UUID NOT NULL REFERENCES public.farm(id),
    boundary geometry(Polygon, 4326)
);
CREATE TABLE public.remote_sensing_job (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id),
    plot_id UUID REFERENCES public.plot(id),
    provider TEXT NOT NULL,
    bbox geometry(Polygon, 4326),
    start_date DATE,
    end_date DATE,
    cloud_max_pct NUMERIC(5,2) DEFAULT 20,
    cadence_days INTEGER NOT NULL DEFAULT 7,
    status TEXT NOT NULL DEFAULT 'active',
    last_run_at TIMESTAMPTZ,
    last_run_status TEXT,
    next_run_at TIMESTAMPTZ,
    observations_fetched INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    lease_owner VARCHAR(150),
    lease_expires_at TIMESTAMPTZ,
    last_error_class VARCHAR(30),
    last_error TEXT
);
CREATE TABLE public.remote_sensing_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plot_id UUID NOT NULL REFERENCES public.plot(id),
    location_id UUID NOT NULL REFERENCES public.location(id),
    observation_date DATE NOT NULL,
    source TEXT,
    ndvi NUMERIC(6,4), ndre NUMERIC(6,4), evi NUMERIC(6,4), savi NUMERIC(6,4),
    canopy_cover_pct NUMERIC(6,2), canopy_height_m NUMERIC(6,2),
    ndwi NUMERIC(6,4), cloud_cover_pct NUMERIC(5,2), metadata JSONB DEFAULT '{}'::JSONB,
    msavi NUMERIC(6,4), satvi NUMERIC(6,4), bsi NUMERIC(6,4), nbr2 NUMERIC(6,4),
    ndti NUMERIC(6,4), lswi NUMERIC(6,4), brightness_index NUMERIC(6,4),
    tc_brightness NUMERIC(8,4), tc_greenness NUMERIC(8,4), tc_wetness NUMERIC(8,4),
    band_blue NUMERIC(6,4), band_green NUMERIC(6,4), band_red NUMERIC(6,4),
    band_nir NUMERIC(6,4), band_swir1 NUMERIC(6,4), band_swir2 NUMERIC(6,4),
    source_system VARCHAR(100), source_id VARCHAR(255), source_raw JSONB,
    schema_version VARCHAR(50), created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);
CREATE UNIQUE INDEX uq_remote_sensing_observation_source
    ON public.remote_sensing_observation (source_system, source_id)
    WHERE source_id IS NOT NULL;
CREATE TABLE public.remote_sensing_provider_attempt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES public.remote_sensing_job(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    outcome TEXT NOT NULL CHECK (outcome IN ('success','no_data','retryable','non_retryable')),
    retryable BOOLEAN,
    observations INTEGER NOT NULL DEFAULT 0 CHECK (observations >= 0),
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    UNIQUE(job_id, attempt_number)
);
CREATE TABLE public.ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system TEXT NOT NULL, source_table TEXT NOT NULL, source_id TEXT NOT NULL,
    target_table TEXT NOT NULL, target_id UUID, operation TEXT NOT NULL,
    payload_hash TEXT NOT NULL, status TEXT NOT NULL, error_message TEXT,
    rows_affected INTEGER NOT NULL DEFAULT 0, processor_version TEXT,
    location_id UUID REFERENCES public.location(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);
CREATE TABLE public.clickhouse_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key TEXT NOT NULL UNIQUE, source_table TEXT NOT NULL, source_id TEXT NOT NULL,
    target_table TEXT NOT NULL, columns JSONB NOT NULL, rows JSONB NOT NULL,
    payload_hash TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);
