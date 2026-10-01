-- ============================================================
-- 358_mobile_private_media.sql
-- Private, device-scoped Field Collector image references.
-- ============================================================

CREATE TABLE IF NOT EXISTS mobile_media_upload (
    media_id                 UUID PRIMARY KEY,
    device_id                VARCHAR(200) NOT NULL REFERENCES mobile_device(device_id),
    user_id                  VARCHAR(200),
    collection_client_id     VARCHAR(200) NOT NULL,
    location_id              UUID NOT NULL REFERENCES location(id),
    object_key                TEXT NOT NULL UNIQUE,
    content_type              TEXT NOT NULL CHECK (content_type = 'image/jpeg'),
    size_bytes                INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 2000000),
    content_sha256            CHAR(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    status                    TEXT NOT NULL DEFAULT 'uploaded'
                              CHECK (status IN ('uploaded', 'attached', 'expired')),
    expires_at                TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    attached_collection_id    UUID REFERENCES offline_collection(id),
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_mobile_media_attachment_state CHECK (
        (status = 'attached') = (attached_collection_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_mobile_media_upload_device_status
    ON mobile_media_upload (device_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mobile_media_upload_client
    ON mobile_media_upload (device_id, collection_client_id, status);
CREATE INDEX IF NOT EXISTS idx_mobile_media_upload_expiry
    ON mobile_media_upload (expires_at)
    WHERE status = 'uploaded';

INSERT INTO schema_version (version, description, applied_by)
VALUES (
    'mobile-private-media-v1',
    'Device-scoped private Field Collector media object references (schema 358)',
    'schema 358'
)
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
