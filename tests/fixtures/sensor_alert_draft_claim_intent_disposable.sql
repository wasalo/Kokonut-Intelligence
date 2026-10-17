-- Minimal draft-claim surface for isolated migration 411 acceptance.

ALTER TABLE public.sensor_reading
    ADD COLUMN reading_date DATE;
UPDATE public.sensor_reading
   SET reading_date = DATE '2026-10-16';

ALTER TABLE public.alert_rule
    ADD COLUMN auto_create_claim BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN claim_type TEXT;
UPDATE public.alert_rule
   SET auto_create_claim = TRUE,
       claim_type = 'sensor_anomaly'
 WHERE id IN (
    'a0000000-0000-0000-0000-000000000051',
    'a0000000-0000-0000-0000-000000000052'
 );

CREATE TABLE public.mrv_claim (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL,
    claim_type VARCHAR(100) NOT NULL,
    claim_date DATE NOT NULL,
    claim_data JSONB NOT NULL,
    source_record_ids UUID[],
    status VARCHAR(50) DEFAULT 'draft',
    reviewer_id UUID,
    review_notes TEXT,
    reviewed_at TIMESTAMPTZ,
    attestation_uid VARCHAR(66),
    attested_at TIMESTAMPTZ,
    sensor_device_id UUID,
    sensor_alert_id UUID,
    source_readings UUID[],
    created_by UUID
);

ALTER TABLE public.sensor_alert
    ADD CONSTRAINT sensor_alert_claim_id_fkey
    FOREIGN KEY (claim_id) REFERENCES public.mrv_claim(id) ON DELETE SET NULL;

-- This row reflects the exact legacy handler shape, including an advanced
-- lifecycle state, so acceptance proves source adoption does not reset review.
INSERT INTO public.mrv_claim (
    id, location_id, claim_type, claim_date, claim_data, status,
    reviewer_id, review_notes, reviewed_at, attestation_uid, attested_at,
    sensor_device_id, sensor_alert_id
) VALUES (
    'a0000000-0000-0000-0000-000000000099',
    'a0000000-0000-0000-0000-000000000001',
    'sensor_anomaly', DATE '2026-10-16',
    '{"sensor_device_id":"a0000000-0000-0000-0000-000000000011",'
     '"alert_id":"a0000000-0000-0000-0000-000000000043",'
     '"reading_value":46.25,"threshold_value":40.0,"severity":"warning"}'::jsonb,
    'verified',
    'a0000000-0000-0000-0000-000000000901',
    'Reviewed before bounded worker rollout',
    '2026-10-16T12:30:00Z',
    '0x' || repeat('a', 64),
    '2026-10-16T13:00:00Z',
    'a0000000-0000-0000-0000-000000000011',
    'a0000000-0000-0000-0000-000000000043'
);
UPDATE public.sensor_alert
   SET claim_id = 'a0000000-0000-0000-0000-000000000099'
 WHERE id = 'a0000000-0000-0000-0000-000000000043';
