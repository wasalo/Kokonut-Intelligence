-- ============================================================
-- 009_operations_ux.sql — Staff-managed operations UX
-- Workflow tracking, evidence management, approval routing
-- ============================================================

-- ============================================================
-- NEW TABLES
-- ============================================================

-- Workflow history: every state transition logged
CREATE TABLE IF NOT EXISTS workflow_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    changed_by UUID,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,
    rejection_reason TEXT
);

CREATE INDEX idx_workflow_history_collection_record ON workflow_history(collection, record_id);
CREATE INDEX idx_workflow_history_to_status ON workflow_history(to_status);
CREATE INDEX idx_workflow_history_changed_at ON workflow_history(changed_at);

-- File upload: structured evidence metadata
CREATE TABLE IF NOT EXISTS file_upload (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    directus_file_id UUID,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    uploaded_by UUID,
    caption TEXT,
    gps_lat NUMERIC(10,7),
    gps_lng NUMERIC(10,7),
    thumbnail_url TEXT,
    linked_collection VARCHAR(100),
    linked_record_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_file_upload_linked ON file_upload(linked_collection, linked_record_id);
CREATE INDEX idx_file_upload_directus ON file_upload(directus_file_id);

-- Approval: cross-cutting approval log
CREATE TABLE IF NOT EXISTS approval (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    approver_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_approval_record ON approval(collection, record_id);
CREATE INDEX idx_approval_approver ON approval(approver_id);

-- ============================================================
-- ALTER EXISTING TABLES — add missing columns
-- ============================================================

-- farm_activity
ALTER TABLE farm_activity ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;

-- harvest_event
ALTER TABLE harvest_event ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;

-- sales_event
ALTER TABLE sales_event ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;

-- expense_event
ALTER TABLE expense_event ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;

-- loss_event
ALTER TABLE loss_event ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;
ALTER TABLE loss_event ADD COLUMN IF NOT EXISTS updated_by UUID;
ALTER TABLE loss_event ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- labor_event
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS updated_by UUID;
ALTER TABLE labor_event ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- field_note
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS updated_by UUID;
ALTER TABLE field_note ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ============================================================
-- ADD MISSING INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_labor_event_location_date ON labor_event(location_id, work_date);
CREATE INDEX IF NOT EXISTS idx_field_note_location_date ON field_note(location_id, note_date);
CREATE INDEX IF NOT EXISTS idx_loss_event_location_date ON loss_event(location_id, loss_date);
CREATE INDEX IF NOT EXISTS idx_field_note_status ON field_note(status);
CREATE INDEX IF NOT EXISTS idx_labor_event_status ON labor_event(status);
