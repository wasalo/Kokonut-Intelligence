-- Extend the 405–413 anomaly fixture with a baseline and demo-cleanup case.
ALTER TABLE public.sensor_alert
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::JSONB;
ALTER TABLE public.sensor_device
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::JSONB;
ALTER TABLE public.alert_rule
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE public.platform_event
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE public.environmental_baseline (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL,
    metric_name TEXT NOT NULL,
    baseline_value NUMERIC,
    unit TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE public.environmental_baseline ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.environmental_baseline FORCE ROW LEVEL SECURITY;

INSERT INTO public.environmental_baseline (
    id, location_id, metric_name, baseline_value, unit
) VALUES (
    'a0000000-0000-0000-0000-000000000201',
    'a0000000-0000-0000-0000-000000000001',
    'soil_moisture', 5, '%'
);

-- This anomalous free-text label must not contaminate the soil baseline: the
-- canonical device/type link identifies this sensor as soil_moisture.
INSERT INTO public.sensor_reading (
    id, sensor_id, location_id, sensor_type, value, reading_date, reading_time,
    quality, metadata, created_at
) VALUES (
    'a0000000-0000-0000-0000-000000000027',
    'a0000000-0000-0000-0000-000000000011',
    'a0000000-0000-0000-0000-000000000001',
    'air_temperature', 10000, CURRENT_DATE, TIME '12:59', 'good',
    '{"mock": true}'::JSONB, NOW() - INTERVAL '1 second'
);

UPDATE public.sensor_device
   SET metadata = '{"mock_sensor_demo": true}'::JSONB
 WHERE id = 'a0000000-0000-0000-0000-000000000011';

UPDATE public.sensor_reading
   SET metadata = COALESCE(metadata, '{}'::JSONB) || '{"mock": true}'::JSONB
 WHERE sensor_id = 'a0000000-0000-0000-0000-000000000011';
