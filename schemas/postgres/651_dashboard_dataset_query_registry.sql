-- Replace arbitrary saved SQL execution with stable, source-controlled query IDs.
-- Existing rows deliberately remain unregistered until their owners select an
-- approved query contract; query_sql is retained for read/export compatibility
-- but the native refresh runner never reads or executes it.
BEGIN;

ALTER TABLE public.dashboard_dataset
    ADD COLUMN IF NOT EXISTS query_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.dashboard_dataset'::regclass
           AND conname = 'dashboard_dataset_query_id_format'
    ) THEN
        ALTER TABLE public.dashboard_dataset
            ADD CONSTRAINT dashboard_dataset_query_id_format
            CHECK (query_id IS NULL OR query_id ~ '^[a-z][a-z0-9_]{0,99}$');
    END IF;
END;
$$;

COMMENT ON COLUMN public.dashboard_dataset.query_id IS
    'Stable source-controlled analytics query contract. NULL or unregistered IDs fail closed; stored query_sql is not executed by the native refresh runner.';

COMMIT;
