-- ============================================================
-- 023_source_lineage_fix.sql — Add missing source lineage columns
-- Fixes: loss_event missing source_raw, labor_event missing source_raw+updated_at+updated_by,
-- field_note missing source_system+source_id+source_raw+updated_at+updated_by+verified_by+verified_at+rejection_reason
-- ============================================================

-- loss_event: add source_raw
ALTER TABLE loss_event ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE loss_event ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE loss_event ADD COLUMN IF NOT EXISTS updated_by UUID;

-- labor_event: add source_raw, updated_at, updated_by, verified_by, verified_at, rejection_reason
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS updated_by UUID;
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS verified_by UUID;
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- field_note: add full source lineage + workflow fields
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS updated_by UUID;
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS verified_by UUID;
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS schema_version VARCHAR(20);
