-- IRI System: Content-addressed identifiers for metadata resolution
-- Enables linked data, metadata graph API, and cross-system interoperability

-- ============================================================
-- iri_registry
-- ============================================================
CREATE TABLE IF NOT EXISTS iri_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    iri TEXT NOT NULL UNIQUE,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    content_hash VARCHAR(128),
    content_hash_type VARCHAR(20) DEFAULT 'raw',
    raw_media_type VARCHAR(50),
    metadata_cid TEXT,
    metadata_json JSONB,
    schema_name VARCHAR(100),
    version INTEGER DEFAULT 1,
    previous_iri TEXT,
    is_current BOOLEAN DEFAULT TRUE,
    chain VARCHAR(50),
    attestation_uid VARCHAR(66),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_iri_entity ON iri_registry(entity_type, entity_id, version);
CREATE INDEX IF NOT EXISTS idx_iri_current ON iri_registry(entity_type, entity_id) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_iri_schema ON iri_registry(schema_name);
CREATE INDEX IF NOT EXISTS idx_iri_type ON iri_registry(entity_type);
CREATE INDEX IF NOT EXISTS idx_iri_attestation ON iri_registry(attestation_uid) WHERE attestation_uid IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_iri_hash_type'
          AND conrelid = 'iri_registry'::regclass
    ) THEN
        ALTER TABLE iri_registry
            ADD CONSTRAINT chk_iri_hash_type CHECK (content_hash_type IN ('raw', 'graph'));
    END IF;
END $$;
