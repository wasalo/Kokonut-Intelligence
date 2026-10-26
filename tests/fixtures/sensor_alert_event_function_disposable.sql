-- Add the source fields used to derive canonical sensor-alert event payloads.

CREATE TABLE public.sensor_type (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL
);
INSERT INTO public.sensor_type (id, name) VALUES
    ('a0000000-0000-0000-0000-000000000071', 'soil_moisture'),
    ('a0000000-0000-0000-0000-000000000072', 'air_temperature');

ALTER TABLE public.location ADD COLUMN name TEXT;
UPDATE public.location SET name = CASE id
    WHEN 'a0000000-0000-0000-0000-000000000001' THEN 'Synthetic Farm One'
    ELSE 'Synthetic Farm Two'
END;

ALTER TABLE public.sensor_device
    ADD COLUMN name TEXT,
    ADD COLUMN sensor_type_id UUID;
UPDATE public.sensor_device SET
    name = CASE id
        WHEN 'a0000000-0000-0000-0000-000000000011' THEN 'Synthetic soil probe'
        ELSE 'Synthetic air probe'
    END,
    sensor_type_id = CASE id
        WHEN 'a0000000-0000-0000-0000-000000000011'
            THEN 'a0000000-0000-0000-0000-000000000071'::uuid
        ELSE 'a0000000-0000-0000-0000-000000000072'::uuid
    END;

ALTER TABLE public.alert_rule
    ADD COLUMN name TEXT,
    ADD COLUMN severity TEXT,
    ADD COLUMN sensor_type_id UUID;
UPDATE public.alert_rule SET
    name = 'Synthetic threshold ' || right(id::TEXT, 3),
    severity = CASE id
        WHEN 'a0000000-0000-0000-0000-000000000052' THEN 'critical'
        ELSE 'warning'
    END,
    sensor_type_id = CASE id
        WHEN 'a0000000-0000-0000-0000-000000000051'
            THEN 'a0000000-0000-0000-0000-000000000071'::uuid
        WHEN 'a0000000-0000-0000-0000-000000000052'
            THEN 'a0000000-0000-0000-0000-000000000071'::uuid
        WHEN 'a0000000-0000-0000-0000-000000000053'
            THEN 'a0000000-0000-0000-0000-000000000071'::uuid
        ELSE 'a0000000-0000-0000-0000-000000000071'::uuid
    END;

ALTER TABLE public.sensor_alert ADD COLUMN claim_id UUID;
UPDATE public.sensor_alert
   SET severity = 'critical',
       message = 'Synthetic critical soil alert',
       reading_value = 46.25,
       threshold_value = 42.0
 WHERE id = 'a0000000-0000-0000-0000-000000000041';

ALTER TABLE public.platform_event
    ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'normal',
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS max_retries INTEGER NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;
