-- Complete data-stream rejection and file lifecycle constraints.

ALTER TABLE data_stream_post
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

ALTER TABLE data_stream_post
    DROP CONSTRAINT IF EXISTS chk_dsp_rejection_reason,
    ADD CONSTRAINT chk_dsp_rejection_reason
        CHECK (status <> 'rejected' OR NULLIF(BTRIM(rejection_reason), '') IS NOT NULL);

ALTER TABLE data_stream_post_comment
    DROP CONSTRAINT IF EXISTS chk_dspc_rejection_reason,
    ADD CONSTRAINT chk_dspc_rejection_reason
        CHECK (status <> 'rejected' OR NULLIF(BTRIM(rejection_reason), '') IS NOT NULL);

ALTER TABLE data_stream_file
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

ALTER TABLE data_stream_file
    DROP CONSTRAINT IF EXISTS chk_dsf_rejection_reason,
    ADD CONSTRAINT chk_dsf_rejection_reason
        CHECK (status <> 'rejected' OR NULLIF(BTRIM(rejection_reason), '') IS NOT NULL);

ALTER TABLE data_stream_file
    DROP CONSTRAINT IF EXISTS chk_dsf_file_size,
    ADD CONSTRAINT chk_dsf_file_size
        CHECK (file_size_bytes IS NULL OR file_size_bytes BETWEEN 0 AND 104857600);
