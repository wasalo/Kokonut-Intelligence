-- Minimal current-weather table with forced RLS for migration 427 acceptance.
-- Location, ingestion_log, outbox, and PostGIS-compatible functions are supplied
-- by weather_forecast_worker_disposable.sql.

CREATE TABLE public.weather_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    observation_date DATE NOT NULL,
    observation_time TIME,
    source VARCHAR(100),
    temperature_c NUMERIC(5,2),
    temp_min_c NUMERIC(5,2),
    temp_max_c NUMERIC(5,2),
    precipitation_mm NUMERIC(8,2),
    rainfall_mm NUMERIC(8,2),
    humidity_pct NUMERIC(5,2),
    wind_speed_kmh NUMERIC(6,2),
    wind_direction_deg NUMERIC(5,2),
    solar_radiation_wm2 NUMERIC(8,2),
    sunshine_hours NUMERIC(5,2),
    cloud_cover_pct NUMERIC(5,2),
    pressure_hpa NUMERIC(8,2),
    visibility_km NUMERIC(6,2),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.weather_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weather_observation FORCE ROW LEVEL SECURITY;
