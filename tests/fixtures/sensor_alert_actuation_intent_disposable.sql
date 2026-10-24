-- Minimal legacy actuation surface plus synthetic alert rules for migration 410.

ALTER TABLE public.alert_rule
    ADD COLUMN actuator_enabled BOOLEAN DEFAULT FALSE,
    ADD COLUMN actuator_type TEXT,
    ADD COLUMN actuator_command TEXT,
    ADD COLUMN actuator_topic TEXT,
    ADD COLUMN human_approval_required BOOLEAN DEFAULT TRUE;

UPDATE public.alert_rule
   SET actuator_enabled = TRUE,
       actuator_type = CASE id
           WHEN 'a0000000-0000-0000-0000-000000000052' THEN 'irrigation'
           WHEN 'a0000000-0000-0000-0000-000000000051' THEN 'pest_control'
           ELSE 'fertilization'
       END,
       actuator_command = CASE id
           WHEN 'a0000000-0000-0000-0000-000000000052' THEN 'open_valve'
           WHEN 'a0000000-0000-0000-0000-000000000051' THEN 'release_beneficial_insects'
           ELSE 'apply_water'
       END,
       actuator_topic = 'legacy/custom/topic',
       human_approval_required = CASE id
           WHEN 'a0000000-0000-0000-0000-000000000051' THEN TRUE
           ELSE FALSE
       END
 WHERE id IN (
    'a0000000-0000-0000-0000-000000000051',
    'a0000000-0000-0000-0000-000000000052',
    'a0000000-0000-0000-0000-000000000054'
 );

INSERT INTO public.sensor_alert (
    id, sensor_device_id, alert_rule_id, reading_id, severity, status, message,
    reading_value, threshold_value, triggered_at, claim_id, location_id
) VALUES
    ('a0000000-0000-0000-0000-000000000043',
     'a0000000-0000-0000-0000-000000000011',
     'a0000000-0000-0000-0000-000000000051',
     'a0000000-0000-0000-0000-000000000021', 'warning', 'open',
     'Synthetic warning with configured approval', 46.25, 40.0,
     '2026-10-16T12:01:00Z', NULL, 'a0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000044',
     'a0000000-0000-0000-0000-000000000011',
     'a0000000-0000-0000-0000-000000000054',
     'a0000000-0000-0000-0000-000000000021', 'warning', 'open',
     'Synthetic warning without configured approval', 46.25, 40.0,
     '2026-10-16T12:02:00Z', NULL, 'a0000000-0000-0000-0000-000000000001');

CREATE TABLE public.actuation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID,
    sensor_alert_id UUID,
    actuator_type VARCHAR(50) NOT NULL,
    actuator_command VARCHAR(100) NOT NULL,
    actuator_topic VARCHAR(255),
    command_payload JSONB NOT NULL,
    trigger_source VARCHAR(100) NOT NULL,
    trigger_alert_severity VARCHAR(20),
    human_approval_required BOOLEAN DEFAULT TRUE,
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    response_received_at TIMESTAMPTZ,
    response_payload JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_actuation_log_status CHECK (status IN (
        'pending', 'requires_approval', 'approved', 'sent', 'acknowledged',
        'executed', 'failed', 'cancelled'
    )),
    CONSTRAINT chk_actuation_log_type CHECK (actuator_type IN (
        'irrigation', 'pest_control', 'fertilization', 'notification', 'custom'
    ))
);

-- A legacy row proves that the additive key leaves historical records intact.
INSERT INTO public.actuation_log (
    id, location_id, sensor_alert_id, actuator_type, actuator_command,
    command_payload, trigger_source, status
) VALUES (
    'a0000000-0000-0000-0000-000000000099',
    'a0000000-0000-0000-0000-000000000002',
    'a0000000-0000-0000-0000-000000000042',
    'irrigation', 'legacy_command', '{"legacy":true}', 'legacy_fixture', 'sent'
);
