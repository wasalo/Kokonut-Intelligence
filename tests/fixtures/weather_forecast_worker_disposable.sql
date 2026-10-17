-- Minimal weather-forecast contract for the signed worker migration check.
-- worker_tenant_context_disposable.sql supplies synthetic tenant/location rows.

ALTER TABLE public.location ADD COLUMN name TEXT;
ALTER TABLE public.location ADD COLUMN center POINT;
UPDATE public.location
   SET name = CASE id
                  WHEN 'a0000000-0000-0000-0000-000000000001'::UUID THEN 'Synthetic A'
                  ELSE 'Synthetic B'
              END,
       center = CASE id
                    WHEN 'a0000000-0000-0000-0000-000000000001'::UUID
                        THEN point(-69.9, 18.5)
                    ELSE point(-70.0, 19.0)
                END;

-- PostGIS is not needed for this bounded fixture. These overloads preserve the
-- ST_X/ST_Y call contract while using PostgreSQL's built-in point type.
CREATE FUNCTION public.st_x(point) RETURNS DOUBLE PRECISION
LANGUAGE SQL IMMUTABLE STRICT
AS $$ SELECT split_part(trim(both '()' FROM $1::TEXT), ',', 1)::DOUBLE PRECISION $$;
CREATE FUNCTION public.st_y(point) RETURNS DOUBLE PRECISION
LANGUAGE SQL IMMUTABLE STRICT
AS $$ SELECT split_part(trim(both '()' FROM $1::TEXT), ',', 2)::DOUBLE PRECISION $$;

CREATE TABLE public.weather_forecast (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL,
    source VARCHAR(100) NOT NULL DEFAULT 'openweathermap',
    forecast_date DATE NOT NULL,
    forecast_hour INTEGER NOT NULL,
    temp_c NUMERIC(5,2),
    temp_min_c NUMERIC(5,2),
    temp_max_c NUMERIC(5,2),
    feels_like_c NUMERIC(5,2),
    humidity_pct NUMERIC(5,2),
    precipitation_mm NUMERIC(8,2),
    precipitation_prob_pct NUMERIC(5,2),
    rain_3h_mm NUMERIC(8,2),
    wind_speed_kmh NUMERIC(6,2),
    wind_direction_deg NUMERIC(5,2),
    wind_gust_kmh NUMERIC(6,2),
    cloud_cover_pct NUMERIC(5,2),
    visibility_km NUMERIC(6,2),
    pressure_hpa NUMERIC(8,2),
    uv_index NUMERIC(5,2),
    description VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (location_id, forecast_date, forecast_hour, source)
);

CREATE TABLE public.ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(100) NOT NULL,
    source_table VARCHAR(100),
    source_id VARCHAR(255),
    target_table VARCHAR(100) NOT NULL,
    target_id UUID,
    operation VARCHAR(50) NOT NULL,
    payload_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    rows_affected INTEGER,
    processing_time_ms INTEGER,
    processor_version VARCHAR(20),
    location_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.clickhouse_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key VARCHAR(255) NOT NULL UNIQUE,
    source_table VARCHAR(100) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    columns JSONB NOT NULL,
    rows JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Exercise the bounded owners with RLS enforced before migration 426 grants
-- any owner-specific policies. Only the disposable fixture uses these flags.
ALTER TABLE public.weather_forecast ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weather_forecast FORCE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log FORCE ROW LEVEL SECURITY;
ALTER TABLE public.clickhouse_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clickhouse_outbox FORCE ROW LEVEL SECURITY;
