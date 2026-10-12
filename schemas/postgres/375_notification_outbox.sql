-- Durable delivery state for notifications produced by platform event handlers.
-- source_event_id is intentionally not an FK: deleting old platform events must
-- not erase queued, delivered, or operator-reviewed notification evidence.
CREATE TABLE IF NOT EXISTS notification_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_event_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    channel VARCHAR(30) NOT NULL CHECK (channel IN ('webhook', 'directus')),
    destination_key VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'retryable', 'succeeded', 'dead_letter', 'resolved', 'discarded')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    retry_cycle_attempts INTEGER NOT NULL DEFAULT 0 CHECK (retry_cycle_attempts >= 0),
    replay_count INTEGER NOT NULL DEFAULT 0 CHECK (replay_count >= 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner VARCHAR(150),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    last_error_class VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    UNIQUE (source_event_id, channel, destination_key),
    CHECK (
        (status = 'processing' AND lease_owner IS NOT NULL
            AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR (status <> 'processing' AND lease_owner IS NULL
            AND lease_token IS NULL AND lease_expires_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_claim
    ON notification_outbox (available_at, created_at, id)
    WHERE status IN ('pending', 'retryable');
CREATE INDEX IF NOT EXISTS idx_notification_outbox_expired_lease
    ON notification_outbox (lease_expires_at)
    WHERE status = 'processing';
CREATE INDEX IF NOT EXISTS idx_notification_outbox_source_event
    ON notification_outbox (source_event_id, event_type);
CREATE INDEX IF NOT EXISTS idx_notification_outbox_dead_letter
    ON notification_outbox (created_at DESC)
    WHERE status = 'dead_letter';

CREATE TABLE IF NOT EXISTS notification_outbox_attempt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbox_id UUID NOT NULL REFERENCES notification_outbox(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    lease_owner VARCHAR(150) NOT NULL,
    lease_token UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing', 'succeeded', 'failed', 'lease_lost')),
    error_class VARCHAR(100),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    UNIQUE (outbox_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_attempt_history
    ON notification_outbox_attempt (outbox_id, attempt_number DESC);

CREATE TABLE IF NOT EXISTS notification_outbox_operator_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbox_id UUID NOT NULL REFERENCES notification_outbox(id),
    action VARCHAR(20) NOT NULL CHECK (action IN ('replayed', 'resolved', 'discarded')),
    actor VARCHAR(255) NOT NULL CHECK (length(btrim(actor)) BETWEEN 1 AND 255),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
    prior_status VARCHAR(20) NOT NULL,
    prior_attempt_count INTEGER NOT NULL CHECK (prior_attempt_count >= 0),
    replay_count INTEGER NOT NULL CHECK (replay_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_operator_history
    ON notification_outbox_operator_audit (outbox_id, created_at);
