-- 345_threat_signal_dedup.sql
-- Add content_hash column to threat_signal for deduplication support.

ALTER TABLE threat_signal
    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(32);

CREATE INDEX IF NOT EXISTS idx_signal_content_hash
    ON threat_signal (content_hash, signal_source, ingested_at)
    WHERE content_hash IS NOT NULL;
