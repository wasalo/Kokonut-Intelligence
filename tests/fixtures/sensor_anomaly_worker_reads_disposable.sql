-- Complete synthetic sensor fields for migration 412 acceptance.
ALTER TABLE public.sensor_reading
    ADD COLUMN IF NOT EXISTS sensor_type TEXT,
    ADD COLUMN IF NOT EXISTS value NUMERIC,
    ADD COLUMN IF NOT EXISTS reading_date DATE,
    ADD COLUMN IF NOT EXISTS reading_time TIME,
    ADD COLUMN IF NOT EXISTS plot_id UUID,
    ADD COLUMN IF NOT EXISTS quality TEXT,
    ADD COLUMN IF NOT EXISTS metadata JSONB,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE public.sensor_device
    ADD COLUMN IF NOT EXISTS endpoint_url TEXT;

UPDATE public.sensor_reading
   SET sensor_type = CASE sensor_id
           WHEN 'a0000000-0000-0000-0000-000000000011' THEN 'soil_moisture'
           ELSE 'air_temperature'
       END,
       value = CASE sensor_id
           WHEN 'a0000000-0000-0000-0000-000000000011' THEN 18
           ELSE 99
       END,
       reading_date = CURRENT_DATE,
       reading_time = TIME '12:00',
       created_at = NOW();

INSERT INTO public.sensor_reading (
    id, sensor_id, location_id, sensor_type, value,
    reading_date, reading_time, created_at
) VALUES
    ('a0000000-0000-0000-0000-000000000023',
     'a0000000-0000-0000-0000-000000000011',
     'a0000000-0000-0000-0000-000000000001',
     'soil_moisture', 4, CURRENT_DATE, TIME '10:00', NOW() - INTERVAL '2 hours'),
    ('a0000000-0000-0000-0000-000000000024',
     'a0000000-0000-0000-0000-000000000011',
     'a0000000-0000-0000-0000-000000000001',
     'soil_moisture', 14, CURRENT_DATE, TIME '11:00', NOW() - INTERVAL '1 hour');

UPDATE public.alert_rule
   SET enabled = FALSE
 WHERE id IN (
     'a0000000-0000-0000-0000-000000000051',
     'a0000000-0000-0000-0000-000000000052',
     'a0000000-0000-0000-0000-000000000053',
     'a0000000-0000-0000-0000-000000000054'
 );

ALTER TABLE public.alert_rule
    ADD COLUMN IF NOT EXISTS metric TEXT,
    ADD COLUMN IF NOT EXISTS operator TEXT,
    ADD COLUMN IF NOT EXISTS threshold_value NUMERIC,
    ADD COLUMN IF NOT EXISTS threshold_value_max NUMERIC,
    ADD COLUMN IF NOT EXISTS cooldown_minutes INTEGER;

INSERT INTO public.alert_rule (
    id, enabled, name, severity, sensor_type_id, metric, operator,
    threshold_value, threshold_value_max, cooldown_minutes,
    auto_create_claim, claim_type
) VALUES
    ('a0000000-0000-0000-0000-000000000091', TRUE, 'Synthetic value rule',
     'warning', 'a0000000-0000-0000-0000-000000000071', 'value', 'gt',
     10, NULL, 60, FALSE, NULL),
    ('a0000000-0000-0000-0000-000000000092', TRUE, 'Synthetic rate rule',
     'warning', 'a0000000-0000-0000-0000-000000000071', 'rate_of_change', 'gt',
     5, NULL, 60, FALSE, NULL),
    ('a0000000-0000-0000-0000-000000000093', TRUE, 'Synthetic gap rule',
     'warning', 'a0000000-0000-0000-0000-000000000071', 'gap', 'lte',
     1, NULL, 60, FALSE, NULL),
    ('a0000000-0000-0000-0000-000000000094', TRUE, 'Synthetic minimum rule',
     'warning', 'a0000000-0000-0000-0000-000000000071', 'min', 'eq',
     4, NULL, 60, FALSE, NULL),
    ('a0000000-0000-0000-0000-000000000095', TRUE, 'Synthetic maximum scope rule',
     'warning', 'a0000000-0000-0000-0000-000000000071', 'max', 'gt',
     50, NULL, 60, FALSE, NULL),
    ('a0000000-0000-0000-0000-000000000096', TRUE, 'Synthetic other sensor rule',
     'warning', 'a0000000-0000-0000-0000-000000000072', 'value', 'gt',
     50, NULL, 60, FALSE, NULL),
    ('a0000000-0000-0000-0000-000000000097', FALSE, 'Synthetic disabled rule',
     'warning', 'a0000000-0000-0000-0000-000000000071', 'value', 'gt',
     0, NULL, 60, FALSE, NULL),
    ('a0000000-0000-0000-0000-000000000098', TRUE, 'Synthetic cooldown rule',
     'warning', 'a0000000-0000-0000-0000-000000000071', 'value', 'gt',
     10, NULL, 60, FALSE, NULL);

INSERT INTO public.sensor_alert (
    id, sensor_device_id, alert_rule_id, reading_id, severity,
    message, triggered_at, location_id
) VALUES (
    'a0000000-0000-0000-0000-000000000046',
    'a0000000-0000-0000-0000-000000000011',
    'a0000000-0000-0000-0000-000000000098',
    'a0000000-0000-0000-0000-000000000021',
    'warning', 'Synthetic cooldown alert', NOW() - INTERVAL '10 minutes',
    'a0000000-0000-0000-0000-000000000001'
);
