-- ============================================================
-- 165_event_bus_durability.sql - Durable event delivery
-- ============================================================

ALTER TABLE platform_event
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(100),
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_platform_event_claimable
    ON platform_event (status, lease_expires_at, created_at);

-- One durable delivery state per event/handler pair. event_handler_log remains
-- the append-only attempt history.
CREATE TABLE IF NOT EXISTS event_handler_delivery (
    event_id UUID NOT NULL REFERENCES platform_event(id) ON DELETE CASCADE,
    handler_id UUID NOT NULL REFERENCES event_handler(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'success', 'error', 'timeout')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, handler_id)
);

CREATE INDEX IF NOT EXISTS idx_event_handler_delivery_status
    ON event_handler_delivery (status, updated_at);

ALTER TABLE event_dead_letter
    ADD COLUMN IF NOT EXISTS disposition VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (disposition IN ('pending', 'replayed', 'resolved', 'discarded')),
    ADD COLUMN IF NOT EXISTS disposition_reason TEXT,
    ADD COLUMN IF NOT EXISTS disposed_by VARCHAR(100),
    ADD COLUMN IF NOT EXISTS disposed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS replayed_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_event_dead_letter_active_event
    ON event_dead_letter (original_event_id) WHERE disposition = 'pending';
