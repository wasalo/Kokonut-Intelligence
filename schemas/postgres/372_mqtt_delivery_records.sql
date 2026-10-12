-- Private off-chain evidence and bounded delivery outcomes. No public API.
CREATE TABLE mqtt_delivery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_key TEXT NOT NULL UNIQUE,
    topic TEXT NOT NULL,
    payload BYTEA NOT NULL CHECK (octet_length(payload) <= 10240),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected', 'failed', 'dead_letter', 'disposed')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_mqtt_delivery_attention ON mqtt_delivery (status, updated_at)
    WHERE status IN ('failed', 'dead_letter', 'rejected');

CREATE TABLE mqtt_delivery_action (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id UUID NOT NULL REFERENCES mqtt_delivery(id),
    action TEXT NOT NULL CHECK (action IN ('replay', 'dispose')),
    actor TEXT NOT NULL CHECK (length(btrim(actor)) > 0),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
