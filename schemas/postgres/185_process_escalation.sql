-- ============================================================
-- 185_process_escalation.sql - Process auto-escalation (BPM handover)
-- ============================================================
-- Records automated escalations raised when a governed process instance
-- is predicted to breach its SLA. An optional draft work_item is created
-- for human follow-up (never auto-verified/published, per agent safety).
-- sweep_and_escalate() is idempotent per open instance.

CREATE TABLE IF NOT EXISTS process_escalation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    work_item_id UUID,
    reason TEXT,
    breach_probability DOUBLE PRECISION,
    escalated_to UUID,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pe_entity ON process_escalation(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_pe_open ON process_escalation(resolved_at);
