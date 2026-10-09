-- Durable validation and batch provenance for field ingestion.

ALTER TABLE ingestion_log
    ADD COLUMN IF NOT EXISTS batch_id UUID,
    ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS validation_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(255),
    ADD COLUMN IF NOT EXISTS received_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE ingestion_log
    DROP CONSTRAINT IF EXISTS chk_ingestion_validation_status,
    ADD CONSTRAINT chk_ingestion_validation_status
        CHECK (validation_status IS NULL OR validation_status IN ('accepted', 'suspect', 'rejected', 'duplicate'));

CREATE INDEX IF NOT EXISTS idx_ingestion_batch ON ingestion_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_dedupe ON ingestion_log(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_ingestion_validation ON ingestion_log(validation_status);
