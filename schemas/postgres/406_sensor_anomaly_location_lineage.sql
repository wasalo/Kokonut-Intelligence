-- Preserve direct location lineage on anomaly receipts and their durable effects.
-- Existing rows that cannot be tied to an authoritative source remain NULL.

BEGIN;

ALTER TABLE public.sensor_alert
    ADD COLUMN IF NOT EXISTS location_id UUID;
ALTER TABLE public.sensor_anomaly_effect
    ADD COLUMN IF NOT EXISTS location_id UUID;
ALTER TABLE public.ingestion_log
    ADD COLUMN IF NOT EXISTS location_id UUID;
ALTER TABLE public.notification_outbox
    ADD COLUMN IF NOT EXISTS location_id UUID;

UPDATE public.sensor_alert AS alert
   SET location_id = device.location_id
  FROM public.sensor_device AS device
 WHERE alert.location_id IS NULL
   AND device.id = alert.sensor_device_id
   AND device.location_id IS NOT NULL
   AND EXISTS (
       SELECT 1
         FROM public.sensor_reading AS reading
        WHERE reading.id = alert.reading_id
          AND reading.location_id = device.location_id
          AND reading.sensor_id::TEXT = device.id::TEXT
   );

UPDATE public.sensor_anomaly_effect AS effect
   SET location_id = reading.location_id
  FROM public.sensor_reading AS reading,
       public.platform_event AS source_event
 WHERE effect.location_id IS NULL
   AND reading.id = effect.source_reading_id
   AND reading.location_id IS NOT NULL
   AND source_event.id = effect.source_event_id
   AND source_event.event_type = 'sensor_reading'
   AND source_event.source_table = 'sensor_reading'
   AND source_event.source_id = reading.id
   AND source_event.payload ->> 'location_id' = reading.location_id::TEXT
   AND (
       source_event.payload ->> 'sensor_id' = reading.sensor_id::TEXT
       OR source_event.payload ->> 'sensor_device_id' = reading.sensor_id::TEXT
   )
   AND (
       source_event.payload ->> 'sensor_id' IS NULL
       OR source_event.payload ->> 'sensor_id' = reading.sensor_id::TEXT
   )
   AND (
       source_event.payload ->> 'sensor_device_id' IS NULL
       OR source_event.payload ->> 'sensor_device_id' = reading.sensor_id::TEXT
   );

UPDATE public.ingestion_log AS log_row
   SET location_id = reading.location_id
  FROM public.sensor_reading AS reading,
       public.sensor_alert AS alert
 WHERE log_row.location_id IS NULL
   AND log_row.source_system = 'anomaly_detector'
   AND log_row.source_table = 'sensor_reading'
   AND log_row.target_table = 'sensor_alert'
   AND log_row.source_id = reading.id::TEXT
   AND alert.id = log_row.target_id
   AND alert.location_id = reading.location_id
   AND reading.location_id IS NOT NULL;

UPDATE public.ingestion_log AS log_row
   SET location_id = alert.location_id
  FROM public.sensor_alert AS alert
 WHERE log_row.location_id IS NULL
   AND log_row.source_system = 'anomaly_detector'
   AND log_row.target_table = 'sensor_alert'
   AND log_row.target_id = alert.id
   AND alert.location_id IS NOT NULL
   AND NOT EXISTS (
       SELECT 1
         FROM public.sensor_reading AS reading
        WHERE reading.id::TEXT = log_row.source_id
   );

UPDATE public.notification_outbox AS outbox
   SET location_id = alert.location_id
  FROM public.platform_event AS source_event,
       public.sensor_alert AS alert
 WHERE outbox.location_id IS NULL
   AND outbox.event_type = 'sensor_alert'
   AND source_event.id = outbox.source_event_id
   AND source_event.event_type = 'sensor_alert'
   AND source_event.source_table = 'sensor_alert'
   AND source_event.source_id = alert.id
   AND alert.location_id IS NOT NULL
   AND source_event.payload ->> 'alert_id' = alert.id::TEXT
   AND source_event.payload ->> 'location_id' = alert.location_id::TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.sensor_alert'::regclass
           AND conname = 'sensor_alert_location_id_fkey'
    ) THEN
        ALTER TABLE public.sensor_alert
            ADD CONSTRAINT sensor_alert_location_id_fkey
            FOREIGN KEY (location_id) REFERENCES public.location(id)
            ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.sensor_anomaly_effect'::regclass
           AND conname = 'sensor_anomaly_effect_location_id_fkey'
    ) THEN
        ALTER TABLE public.sensor_anomaly_effect
            ADD CONSTRAINT sensor_anomaly_effect_location_id_fkey
            FOREIGN KEY (location_id) REFERENCES public.location(id)
            ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.ingestion_log'::regclass
           AND conname = 'ingestion_log_location_id_fkey'
    ) THEN
        ALTER TABLE public.ingestion_log
            ADD CONSTRAINT ingestion_log_location_id_fkey
            FOREIGN KEY (location_id) REFERENCES public.location(id)
            ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.notification_outbox'::regclass
           AND conname = 'notification_outbox_location_id_fkey'
    ) THEN
        ALTER TABLE public.notification_outbox
            ADD CONSTRAINT notification_outbox_location_id_fkey
            FOREIGN KEY (location_id) REFERENCES public.location(id)
            ON DELETE SET NULL;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_sensor_alert_location
    ON public.sensor_alert(location_id);
CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_effect_location
    ON public.sensor_anomaly_effect(location_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_location
    ON public.ingestion_log(location_id);
CREATE INDEX IF NOT EXISTS idx_notification_outbox_location
    ON public.notification_outbox(location_id);

COMMENT ON COLUMN public.sensor_alert.location_id IS
    'Direct farm scope for alert authorization; unresolved historical rows remain NULL.';
COMMENT ON COLUMN public.sensor_anomaly_effect.location_id IS
    'Source-reading location used for tenant-scoped anomaly idempotency.';
COMMENT ON COLUMN public.ingestion_log.location_id IS
    'Optional direct farm scope for location-bound ingestion audit records.';
COMMENT ON COLUMN public.notification_outbox.location_id IS
    'Optional direct farm scope for location-bound delivery intents; NULL does not authorize tenant access.';

COMMIT;
