-- Allow exact idempotent seed replays without permitting published mutations.

CREATE OR REPLACE FUNCTION enforce_data_stream_post_publication()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'published'
       AND OLD IS DISTINCT FROM NEW THEN
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
    IF TG_OP = 'UPDATE' AND OLD.status = 'published'
       AND OLD IS DISTINCT FROM NEW THEN
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
