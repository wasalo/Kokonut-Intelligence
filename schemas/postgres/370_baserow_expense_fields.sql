-- 370_baserow_expense_fields.sql
-- Add separate source-reported payment state and people count to expense events.
-- The workflow status remains independent; no source records are written here.

BEGIN;

ALTER TABLE expense_event
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
        ALTER TABLE expense_event
            ADD CONSTRAINT chk_expense_event_people_impacted_count_nonnegative
            CHECK (people_impacted_count IS NULL OR people_impacted_count >= 0);
    END IF;
END;
$$;

COMMENT ON COLUMN expense_event.payment_status IS
    'Source-reported payment settlement state; separate from the expense workflow status.';
COMMENT ON COLUMN expense_event.people_impacted_count IS
    'Nullable source-reported count of people associated with this expense; not a person identity or verified impact metric.';

COMMIT;
