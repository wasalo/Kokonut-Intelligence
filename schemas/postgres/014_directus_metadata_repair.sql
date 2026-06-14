-- ============================================================
-- 014_directus_metadata_repair.sql — Directus metadata drift repair
-- ============================================================

-- Guard: skip entirely if Directus tables are not installed
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'directus_collections'
  ) THEN
    RAISE NOTICE 'Skipping 014_directus_metadata_repair: Directus not installed';
    RETURN;
  END IF;
END $$;

DO $$ BEGIN
  -- Directus treats collection sort_field as a real item column. Clear invalid
  -- sort fields so API/GraphQL queries do not request fields that do not exist.
  UPDATE directus_collections dc
  SET sort_field = NULL
  WHERE dc.sort_field IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = dc.collection
          AND c.column_name = dc.sort_field
    );

  -- Remove stale non-alias field metadata for columns that no longer exist in
  -- PostgreSQL. Alias fields are virtual Directus fields and are intentionally
  -- excluded from this cleanup.
  DELETE FROM directus_fields df
  WHERE EXISTS (
        SELECT 1
        FROM information_schema.tables t
        WHERE t.table_schema = 'public'
          AND t.table_name = df.collection
    )
    AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = df.collection
          AND c.column_name = df.field
    )
    AND COALESCE(df.special, '') NOT LIKE '%alias%';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'Skipping 014_directus_metadata_repair: %', SQLERRM;
END $$;
