-- 063_statement_of_work.sql
-- Statement of Work Production: SOW document, deliverables, payment schedule, change requests

BEGIN;

-- ============================================================================
-- STATEMENT OF WORK
-- ============================================================================

CREATE TABLE IF NOT EXISTS statement_of_work (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    sow_name VARCHAR(255) NOT NULL,
    sow_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    effective_date DATE NOT NULL,
    expiration_date DATE,
    client_name VARCHAR(255),
    contractor_name VARCHAR(255),
    total_contract_value NUMERIC(15,2) DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    payment_terms TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'active', 'completed', 'terminated')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_sow_location ON statement_of_work(location_id);
CREATE INDEX IF NOT EXISTS idx_sow_status ON statement_of_work(status);

CREATE TRIGGER trg_sow_updated_at
    BEFORE UPDATE ON statement_of_work
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE statement_of_work IS 'Statement of Work documents with parties, terms, and project scope';

-- ============================================================================
-- SOW DELIVERABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS sow_deliverable (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sow_id UUID NOT NULL REFERENCES statement_of_work(id) ON DELETE CASCADE,
    deliverable_name VARCHAR(255) NOT NULL,
    description TEXT,
    acceptance_criteria TEXT,
    due_date DATE,
    delivered_at DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'delivered', 'accepted', 'rejected')),
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sow_deliverable_sow ON sow_deliverable(sow_id);
CREATE INDEX IF NOT EXISTS idx_sow_deliverable_status ON sow_deliverable(status);

CREATE TRIGGER trg_sow_deliverable_updated_at
    BEFORE UPDATE ON sow_deliverable
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE sow_deliverable IS 'SOW deliverables with acceptance criteria and delivery tracking';

-- ============================================================================
-- SOW PAYMENT SCHEDULE
-- ============================================================================

CREATE TABLE IF NOT EXISTS sow_payment_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sow_id UUID NOT NULL REFERENCES statement_of_work(id) ON DELETE CASCADE,
    milestone_name VARCHAR(255) NOT NULL,
    amount NUMERIC(15,2) NOT NULL,
    due_date DATE,
    payment_status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (payment_status IN ('pending', 'paid', 'overdue', 'cancelled')),
    invoice_number VARCHAR(100),
    paid_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sow_payment_sow ON sow_payment_schedule(sow_id);
CREATE INDEX IF NOT EXISTS idx_sow_payment_status ON sow_payment_schedule(payment_status);

CREATE TRIGGER trg_sow_payment_updated_at
    BEFORE UPDATE ON sow_payment_schedule
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE sow_payment_schedule IS 'SOW payment milestones with due dates and invoice tracking';

-- ============================================================================
-- SOW CHANGE REQUEST
-- ============================================================================

CREATE TABLE IF NOT EXISTS sow_change_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sow_id UUID NOT NULL REFERENCES statement_of_work(id) ON DELETE CASCADE,
    change_name VARCHAR(255) NOT NULL,
    description TEXT,
    impact_on_timeline TEXT,
    impact_on_budget NUMERIC(15,2),
    requested_by VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'rejected', 'implemented')),
    decided_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sow_change_sow ON sow_change_request(sow_id);
CREATE INDEX IF NOT EXISTS idx_sow_change_status ON sow_change_request(status);

CREATE TRIGGER trg_sow_change_updated_at
    BEFORE UPDATE ON sow_change_request
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE sow_change_request IS 'SOW change requests with impact assessment and approval workflow';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public SOW summary (gated: registry + status filter + PII stripped)
CREATE OR REPLACE VIEW v_public_statement_of_work AS
SELECT
    s.id,
    s.location_id,
    l.name AS location_name,
    s.sow_name,
    s.sow_version,
    s.effective_date,
    s.expiration_date,
    s.total_contract_value,
    s.currency,
    s.status,
    (SELECT COUNT(*)::int FROM sow_deliverable sd WHERE sd.sow_id = s.id) AS total_deliverables,
    (SELECT COUNT(*)::int FROM sow_deliverable sd WHERE sd.sow_id = s.id AND sd.status = 'accepted') AS accepted_deliverables,
    (SELECT COUNT(*)::int FROM sow_payment_schedule sp WHERE sp.sow_id = s.id) AS total_payments,
    (SELECT COALESCE(SUM(sp.amount), 0) FROM sow_payment_schedule sp WHERE sp.sow_id = s.id AND sp.payment_status = 'paid') AS total_paid,
    (SELECT COUNT(*)::int FROM sow_change_request sc WHERE sc.sow_id = s.id) AS total_change_requests,
    s.created_at
FROM statement_of_work s
JOIN location l ON s.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND s.status IN ('active', 'completed')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 2. Public SOW deliverables (gated: registry + SOW status filter)
CREATE OR REPLACE VIEW v_public_sow_deliverables AS
SELECT
    sd.id,
    sd.sow_id,
    s.sow_name,
    s.location_id,
    l.name AS location_name,
    sd.deliverable_name,
    sd.description,
    sd.acceptance_criteria,
    sd.due_date,
    sd.delivered_at,
    sd.status,
    CASE
        WHEN sd.due_date IS NOT NULL AND sd.delivered_at IS NOT NULL
        THEN sd.delivered_at <= sd.due_date
        ELSE NULL
    END AS on_time,
    sd.created_at
FROM sow_deliverable sd
JOIN statement_of_work s ON sd.sow_id = s.id
JOIN location l ON s.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND s.status IN ('active', 'completed')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 3. Public SOW payment schedule (gated: registry + SOW status filter + invoice stripped)
CREATE OR REPLACE VIEW v_public_sow_payment_schedule AS
SELECT
    sp.id,
    sp.sow_id,
    s.sow_name,
    s.location_id,
    l.name AS location_name,
    sp.milestone_name,
    sp.amount,
    s.currency,
    sp.due_date,
    sp.payment_status,
    CASE
        WHEN sp.payment_status = 'paid' AND sp.paid_at IS NOT NULL AND sp.due_date IS NOT NULL
        THEN sp.paid_at::date <= sp.due_date
        ELSE NULL
    END AS on_time,
    sp.created_at
FROM sow_payment_schedule sp
JOIN statement_of_work s ON sp.sow_id = s.id
JOIN location l ON s.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND s.status IN ('active', 'completed')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

COMMIT;
