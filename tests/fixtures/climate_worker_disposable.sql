-- Minimal forced-RLS contract for migration 429. The parent fixture is
-- worker_tenant_context_disposable.sql and supplies synthetic org/location rows.

CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE public.location
    ADD COLUMN latitude DOUBLE PRECISION,
    ADD COLUMN longitude DOUBLE PRECISION,
    ADD COLUMN center geometry(Point, 4326);
UPDATE public.location
   SET latitude = CASE id
           WHEN 'a0000000-0000-0000-0000-000000000001'::UUID THEN 18.5
           ELSE 19.0
       END,
       longitude = CASE id
           WHEN 'a0000000-0000-0000-0000-000000000001'::UUID THEN -69.9
           ELSE -70.0
       END,
       center = public.ST_SetSRID(public.ST_MakePoint(
           CASE id
               WHEN 'a0000000-0000-0000-0000-000000000001'::UUID THEN -69.9
               ELSE -70.0
           END,
           CASE id
               WHEN 'a0000000-0000-0000-0000-000000000001'::UUID THEN 18.5
               ELSE 19.0
           END
       ), 4326);

CREATE TABLE public.farm (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id)
);
CREATE TABLE public.plot (
    id UUID PRIMARY KEY,
    farm_id UUID NOT NULL REFERENCES public.farm(id),
    boundary geometry(Polygon, 4326)
);
INSERT INTO public.farm (id, location_id)
VALUES ('a0000000-0000-0000-0000-000000000901', 'a0000000-0000-0000-0000-000000000001');
INSERT INTO public.plot (id, farm_id, boundary)
VALUES (
    'a0000000-0000-0000-0000-000000000902',
    'a0000000-0000-0000-0000-000000000901',
    public.ST_GeomFromText('POLYGON((-70 18,-69 18,-69 19,-70 19,-70 18))', 4326)
);

CREATE TABLE public.worldclim_climate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.location(id),
    plot_id UUID,
    bio1_mean_annual_temp NUMERIC(6,2),
    bio4_temp_seasonality NUMERIC(8,2),
    bio5_max_temp_warmest_month NUMERIC(6,2),
    bio6_min_temp_coldest_month NUMERIC(6,2),
    bio12_annual_precipitation NUMERIC(8,2),
    bio15_precip_seasonality NUMERIC(6,2),
    bio16_precip_wettest_quarter NUMERIC(8,2),
    bio17_precip_driest_quarter NUMERIC(8,2),
    temp_range NUMERIC(6,2),
    source VARCHAR(100),
    resolution_m INTEGER,
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT statement_timestamp()
);
CREATE UNIQUE INDEX uq_worldclim_climate_location_baseline
    ON public.worldclim_climate(location_id) WHERE plot_id IS NULL;

CREATE TABLE public.ncep_weather_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL,
    plot_id UUID, target_date DATE NOT NULL, source VARCHAR(100), resolution_m INTEGER,
    soil_moisture_6m NUMERIC(8,4), mean_temp_6m NUMERIC(6,2),
    max_temp_6m NUMERIC(6,2), min_temp_6m NUMERIC(6,2),
    precipitation_6m NUMERIC(8,2), metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT statement_timestamp()
);
CREATE TABLE public.modis_lst_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL,
    plot_id UUID, target_date DATE NOT NULL, source VARCHAR(100), resolution_m INTEGER,
    lst_day_mean_6m NUMERIC(6,2), lst_night_mean_6m NUMERIC(6,2),
    metadata JSONB DEFAULT '{}', updated_at TIMESTAMPTZ DEFAULT statement_timestamp()
);
CREATE TABLE public.smap_soil_moisture (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL,
    plot_id UUID, target_date DATE NOT NULL, source VARCHAR(100), resolution_m INTEGER,
    soil_moisture_6m NUMERIC(8,4), metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT statement_timestamp()
);
CREATE TABLE public.sentinel1_sar_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL,
    plot_id UUID, target_date DATE NOT NULL, source VARCHAR(100), resolution_m INTEGER,
    vh_median_6m NUMERIC(8,4), vv_median_6m NUMERIC(8,4), metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT statement_timestamp()
);
CREATE TABLE public.ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_system VARCHAR(100) NOT NULL,
    source_table VARCHAR(100), source_id VARCHAR(255), target_table VARCHAR(100) NOT NULL,
    target_id UUID, operation VARCHAR(50) NOT NULL, payload_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'success', error_message TEXT,
    rows_affected INTEGER, processing_time_ms INTEGER, processor_version VARCHAR(20),
    location_id UUID, created_at TIMESTAMPTZ DEFAULT statement_timestamp()
);

ALTER TABLE public.farm ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.farm FORCE ROW LEVEL SECURITY;
ALTER TABLE public.plot ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plot FORCE ROW LEVEL SECURITY;
ALTER TABLE public.worldclim_climate ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.worldclim_climate FORCE ROW LEVEL SECURITY;
ALTER TABLE public.ncep_weather_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ncep_weather_summary FORCE ROW LEVEL SECURITY;
ALTER TABLE public.modis_lst_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.modis_lst_summary FORCE ROW LEVEL SECURITY;
ALTER TABLE public.smap_soil_moisture ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.smap_soil_moisture FORCE ROW LEVEL SECURITY;
ALTER TABLE public.sentinel1_sar_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sentinel1_sar_summary FORCE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log FORCE ROW LEVEL SECURITY;
