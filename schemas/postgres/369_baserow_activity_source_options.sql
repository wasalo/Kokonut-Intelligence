-- ============================================================
-- 369_baserow_activity_source_options.sql
-- Preserve source activity selections separately from canonical type.
-- This adds schema only; it performs no source projection or import.
-- ============================================================

BEGIN;

ALTER TABLE public.farm_activity
    ADD COLUMN IF NOT EXISTS activity_type_source_options JSONB;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_farm_activity_activity_type_source_options_array'
          AND conrelid = 'public.farm_activity'::regclass
    ) THEN
        ALTER TABLE public.farm_activity
            ADD CONSTRAINT chk_farm_activity_activity_type_source_options_array
            CHECK (
                activity_type_source_options IS NULL
                OR jsonb_typeof(activity_type_source_options) = 'array'
            );
    END IF;
END
$$;

COMMENT ON COLUMN public.farm_activity.activity_type_source_options IS
    'Ordered source selections for activity_type, preserving each source option ID and exact label; does not determine the canonical activity_type.';

COMMIT;
