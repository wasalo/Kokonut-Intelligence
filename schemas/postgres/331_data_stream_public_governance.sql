-- Tranche 1: fail-closed data-stream publication and public projections.

ALTER TABLE data_stream_post_comment
    ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) NOT NULL DEFAULT 'private',
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS updated_by UUID;

ALTER TABLE data_stream_file
    ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) NOT NULL DEFAULT 'private',
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS created_by UUID,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_by UUID,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deleted_by UUID,
    ADD COLUMN IF NOT EXISTS deletion_reason TEXT;

ALTER TABLE data_stream_post_comment
    ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE data_stream_file
    ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE data_stream_post_comment
    DROP CONSTRAINT IF EXISTS chk_dspc_status,
    ADD CONSTRAINT chk_dspc_status
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE data_stream_post_comment
    DROP CONSTRAINT IF EXISTS chk_dspc_visibility,
    ADD CONSTRAINT chk_dspc_visibility
        CHECK (visibility IN ('public', 'internal', 'private'));

ALTER TABLE data_stream_file
    DROP CONSTRAINT IF EXISTS chk_dsf_status,
    ADD CONSTRAINT chk_dsf_status
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE data_stream_file
    DROP CONSTRAINT IF EXISTS chk_dsf_visibility,
    ADD CONSTRAINT chk_dsf_visibility
        CHECK (visibility IN ('public', 'internal', 'private'));

ALTER TABLE data_stream_file
    DROP CONSTRAINT IF EXISTS chk_dsf_coordinates,
    ADD CONSTRAINT chk_dsf_coordinates
        CHECK (
            (latitude IS NULL AND longitude IS NULL)
            OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
        );

CREATE OR REPLACE FUNCTION data_stream_post_is_public(p_post_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM data_stream_post dsp
        JOIN location l ON l.id = dsp.location_id
        WHERE dsp.id = p_post_id
          AND dsp.status IN ('verified', 'published')
          AND dsp.visibility = 'public'
          AND COALESCE(dsp.metadata ->> 'privacy', '') = 'public_summary'
          AND l.status = 'active'
          AND EXISTS (
              SELECT 1
              FROM farm_registry_record fr
              WHERE fr.location_id = dsp.location_id
                AND fr.status IN ('verified', 'published')
          )
    );
$$;

CREATE OR REPLACE FUNCTION enforce_data_stream_post_publication()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'published' THEN
        RAISE EXCEPTION 'published data stream posts are immutable';
    END IF;

    IF NEW.status IN ('verified', 'published')
       AND NEW.visibility = 'public'
       AND COALESCE(NEW.metadata ->> 'privacy', '') <> 'public_summary' THEN
        RAISE EXCEPTION 'public data stream posts require metadata.privacy=public_summary';
    END IF;

    IF NEW.status = 'published' AND NOT EXISTS (
        SELECT 1
        FROM location l
        WHERE l.id = NEW.location_id
          AND l.status = 'active'
          AND EXISTS (
              SELECT 1
              FROM farm_registry_record fr
              WHERE fr.location_id = NEW.location_id
                AND fr.status IN ('verified', 'published')
          )
    ) THEN
        RAISE EXCEPTION 'data stream post is not eligible for publication';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_data_stream_attachment_publication()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'published' THEN
        RAISE EXCEPTION 'published data stream attachments are immutable';
    END IF;

    IF NEW.status = 'published' THEN
        IF NEW.visibility <> 'public'
           OR COALESCE(NEW.metadata ->> 'privacy', '') <> 'public_summary'
           OR NOT data_stream_post_is_public(NEW.post_id) THEN
            RAISE EXCEPTION 'data stream attachment is not eligible for publication';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_data_stream_post_publication ON data_stream_post;
CREATE TRIGGER trg_data_stream_post_publication
    BEFORE INSERT OR UPDATE ON data_stream_post
    FOR EACH ROW
    EXECUTE FUNCTION enforce_data_stream_post_publication();

DROP TRIGGER IF EXISTS trg_data_stream_comment_publication ON data_stream_post_comment;
CREATE TRIGGER trg_data_stream_comment_publication
    BEFORE INSERT OR UPDATE ON data_stream_post_comment
    FOR EACH ROW
    EXECUTE FUNCTION enforce_data_stream_attachment_publication();

DROP TRIGGER IF EXISTS trg_data_stream_file_publication ON data_stream_file;
CREATE TRIGGER trg_data_stream_file_publication
    BEFORE INSERT OR UPDATE ON data_stream_file
    FOR EACH ROW
    EXECUTE FUNCTION enforce_data_stream_attachment_publication();

CREATE OR REPLACE VIEW v_project_data_stream AS
SELECT
    dsp.id,
    dsp.location_id,
    dsp.post_type,
    dsp.title,
    dsp.content,
    dsp.media_type,
    dsp.evidence_urls,
    dsp.file_ids,
    dsp.visibility,
    dsp.status,
    dsp.is_anchored,
    dsp.attestation_uid,
    dsp.chain,
    dsp.anchored_at,
    dsp.created_at,
    dsp.created_by,
    dsp.metadata,
    l.name AS location_name,
    fm.name AS farm_name,
    (
        SELECT COUNT(*)
        FROM data_stream_post_comment dsc
        WHERE dsc.post_id = dsp.id
          AND dsc.status = 'published'
          AND dsc.visibility = 'public'
          AND COALESCE(dsc.metadata ->> 'privacy', '') = 'public_summary'
    ) AS comment_count
FROM data_stream_post dsp
JOIN location l ON l.id = dsp.location_id
LEFT JOIN farm_registry_record fr
    ON fr.location_id = dsp.location_id
   AND fr.status IN ('verified', 'published')
LEFT JOIN farm fm ON fm.id = fr.farm_id
WHERE data_stream_post_is_public(dsp.id)
ORDER BY dsp.created_at DESC;

CREATE OR REPLACE VIEW v_data_stream_search AS
SELECT
    dsp.id,
    dsp.location_id,
    dsp.post_type,
    dsp.title,
    dsp.content,
    dsp.visibility,
    dsp.status,
    dsp.created_at,
    l.name AS location_name,
    ts_rank(
        dsp.content_search,
        plainto_tsquery('english', COALESCE(dsp.title, '') || ' ' || COALESCE(dsp.content, ''))
    ) AS search_rank
FROM data_stream_post dsp
JOIN location l ON l.id = dsp.location_id
WHERE data_stream_post_is_public(dsp.id)
  AND dsp.content_search IS NOT NULL;

CREATE OR REPLACE VIEW v_data_stream_public_file AS
SELECT dsf.*
FROM data_stream_file dsf
WHERE dsf.status = 'published'
  AND dsf.visibility = 'public'
  AND COALESCE(dsf.metadata ->> 'privacy', '') = 'public_summary'
  AND data_stream_post_is_public(dsf.post_id)
  AND dsf.deleted_at IS NULL;
