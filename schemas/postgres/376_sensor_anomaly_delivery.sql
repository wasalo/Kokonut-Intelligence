-- Per-reading/rule receipts make sensor anomaly effects safe to replay.
-- No source event or sensor row FK: receipts must survive event cleanup and
-- preserve duplicate suppression if source data is later archived.

ALTER TABLE notification_outbox
    DROP CONSTRAINT IF EXISTS notification_outbox_channel_check;
ALTER TABLE notification_outbox
    ADD CONSTRAINT notification_outbox_channel_check
    CHECK (channel IN ('webhook', 'directus', 'email'));

CREATE TABLE IF NOT EXISTS sensor_anomaly_effect (
    source_reading_id UUID NOT NULL,
    alert_rule_id UUID NOT NULL,
    source_event_id UUID NOT NULL,
    outcome VARCHAR(20) NOT NULL
        CHECK (outcome IN ('no_match', 'cooldown', 'alert_created')),
    sensor_alert_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_reading_id, alert_rule_id),
    UNIQUE (source_event_id, alert_rule_id),
    CHECK ((outcome = 'alert_created' AND sensor_alert_id IS NOT NULL)
        OR (outcome <> 'alert_created' AND sensor_alert_id IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_effect_event
    ON sensor_anomaly_effect (source_event_id);
CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_effect_alert
    ON sensor_anomaly_effect (sensor_alert_id)
    WHERE sensor_alert_id IS NOT NULL;

-- Critical actuation remains pending human approval. The legacy constraint
-- omitted this status even though the sender has always attempted to record it.
ALTER TABLE actuation_log
    DROP CONSTRAINT IF EXISTS chk_actuation_log_status;
ALTER TABLE actuation_log
    ADD CONSTRAINT chk_actuation_log_status CHECK (
        status IN (
            'pending', 'requires_approval', 'approved', 'sent', 'acknowledged',
            'executed', 'failed', 'cancelled'
        )
    );
