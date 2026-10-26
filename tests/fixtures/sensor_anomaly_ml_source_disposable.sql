-- Synthetic tenant sensor rows for migration 650 acceptance only.
CREATE TABLE public.sensor_device (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL,
    slug TEXT NOT NULL
);

CREATE TABLE public.sensor_reading (
    id UUID PRIMARY KEY,
    sensor_id UUID NOT NULL,
    location_id UUID NOT NULL,
    sensor_type TEXT NOT NULL,
    reading_date DATE NOT NULL,
    reading_time TIME,
    value NUMERIC(12, 4) NOT NULL,
    quality TEXT NOT NULL
);

INSERT INTO public.sensor_device (id, location_id, slug) VALUES
    ('a0000000-0000-0000-0000-000000000011',
     'a0000000-0000-0000-0000-000000000001', 'synthetic-location-a'),
    ('a0000000-0000-0000-0000-000000000012',
     'a0000000-0000-0000-0000-000000000002', 'synthetic-location-b');

INSERT INTO public.sensor_reading (
    id, sensor_id, location_id, sensor_type, reading_date,
    reading_time, value, quality
) VALUES
    ('a0000000-0000-0000-0000-000000000021',
     'a0000000-0000-0000-0000-000000000011',
     'a0000000-0000-0000-0000-000000000001', 'soil_moisture', CURRENT_DATE,
     TIME '10:00', 21, 'good'),
    ('a0000000-0000-0000-0000-000000000022',
     'a0000000-0000-0000-0000-000000000012',
     'a0000000-0000-0000-0000-000000000002', 'soil_moisture', CURRENT_DATE,
     TIME '10:00', 99, 'good'),
    ('a0000000-0000-0000-0000-000000000023',
     'a0000000-0000-0000-0000-000000000011',
     'a0000000-0000-0000-0000-000000000001', 'soil_moisture', CURRENT_DATE,
     TIME '11:00', 5, 'suspect');

ALTER TABLE public.sensor_device ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sensor_device FORCE ROW LEVEL SECURITY;
ALTER TABLE public.sensor_reading ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sensor_reading FORCE ROW LEVEL SECURITY;
