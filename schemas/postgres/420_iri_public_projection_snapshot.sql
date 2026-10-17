-- Store an explicitly published, allowlisted public snapshot per location IRI.
-- Private metadata_json and stored content_hash remain separate and are never
-- used by the native public Gateway resolver.

ALTER TABLE iri_registry
    ADD COLUMN IF NOT EXISTS public_projection JSONB;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_iri_public_projection_object'
          AND conrelid = 'iri_registry'::regclass
    ) THEN
        ALTER TABLE iri_registry
            ADD CONSTRAINT chk_iri_public_projection_object
            CHECK (
                public_projection IS NULL
                OR jsonb_typeof(public_projection) = 'object'
            );
    END IF;
END $$;

COMMENT ON COLUMN iri_registry.public_projection IS
    'Explicitly published allowlisted location projection; never copied from metadata_json.';
