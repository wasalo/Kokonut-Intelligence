-- ============================================================
-- 368_baserow_expense_and_farm_crop_schema_draft.sql
-- Repository-only targets approved for Baserow reconciliation.
-- No source rows or relationships are imported by this migration.
-- ============================================================

BEGIN;

ALTER TABLE public.expense_event
    ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50),
    ADD COLUMN IF NOT EXISTS people_impacted_count INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_expense_event_people_impacted_count_nonnegative'
          AND conrelid = 'public.expense_event'::regclass
    ) THEN
        ALTER TABLE public.expense_event
            ADD CONSTRAINT chk_expense_event_people_impacted_count_nonnegative
            CHECK (people_impacted_count IS NULL OR people_impacted_count >= 0);
    END IF;
END
$$;

COMMENT ON COLUMN public.expense_event.payment_status IS
    'Payment settlement state, separate from workflow status; source option mappings are not implied.';
COMMENT ON COLUMN public.expense_event.people_impacted_count IS
    'Reported count of people per expense; nullable and nonnegative; not a governed impact metric or unique-person count.';

CREATE TABLE IF NOT EXISTS public.farm_crop (
    farm_id UUID NOT NULL REFERENCES public.farm(id) ON DELETE RESTRICT,
    crop_id UUID NOT NULL REFERENCES public.crop(id) ON DELETE RESTRICT,
    source_system TEXT,
    source_database_id BIGINT,
    source_table_id BIGINT,
    source_field_id BIGINT,
    source_row_id BIGINT,
    source_related_table_id BIGINT,
    source_related_row_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_farm_crop PRIMARY KEY (farm_id, crop_id),
    CONSTRAINT chk_farm_crop_source_provenance_complete CHECK (
        (
            source_system IS NULL
            AND source_database_id IS NULL
            AND source_table_id IS NULL
            AND source_field_id IS NULL
            AND source_row_id IS NULL
            AND source_related_table_id IS NULL
            AND source_related_row_id IS NULL
        )
        OR
        (
            source_system IS NOT NULL
            AND BTRIM(source_system) <> ''
            AND source_database_id IS NOT NULL AND source_database_id > 0
            AND source_table_id IS NOT NULL AND source_table_id > 0
            AND source_field_id IS NOT NULL AND source_field_id > 0
            AND source_row_id IS NOT NULL AND source_row_id > 0
            AND source_related_table_id IS NOT NULL AND source_related_table_id > 0
            AND source_related_row_id IS NOT NULL AND source_related_row_id > 0
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_farm_crop_source_edge
    ON public.farm_crop (
        source_system,
        source_database_id,
        source_table_id,
        source_field_id,
        source_row_id,
        source_related_table_id,
        source_related_row_id
    )
    WHERE source_system IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_farm_crop_crop_id
    ON public.farm_crop (crop_id);

COMMENT ON TABLE public.farm_crop IS
    'Many-to-many farm-to-crop-type association; distinct from seasonal crop_cycle records. Optional source-edge provenance must be complete when present.';
COMMENT ON COLUMN public.farm_crop.source_field_id IS
    'Canonical source edge is emitted from the Farm.Species side; its reciprocal is validated, not inserted twice.';

COMMIT;
