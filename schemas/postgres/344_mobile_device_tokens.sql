-- ============================================================
-- Mobile field collector device tokens
-- ============================================================

ALTER TABLE mobile_device
    ADD COLUMN IF NOT EXISTS device_token_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mobile_device_token_hash
    ON mobile_device (device_token_hash)
    WHERE device_token_hash IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_offline_collection_client_id
    ON offline_collection (client_id)
    WHERE client_id IS NOT NULL;
