-- ============================================================
-- 182_process_mining.sql - Process mining for the lifecycle ledger
-- ============================================================
-- Turns the generic lifecycle_transition ledger (179) into a
-- process-mining source of truth: discovered process variants,
-- conformance classification, and case-level timelines. Reads
-- only; process_mining.py computes variants and may persist the
-- discovered set into process_variant for trend tracking.
--
-- Defines the canonical 5-state publication model so conformance
-- can be checked uniformly across every governed entity type.

CREATE TABLE IF NOT EXISTS process_variant (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    variant_signature TEXT NOT NULL,
    step_sequence JSONB NOT NULL,
    instance_count INTEGER NOT NULL DEFAULT 0,
    is_conforming BOOLEAN NOT NULL DEFAULT TRUE,
    conformance_notes JSONB DEFAULT '[]'::jsonb,
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_type, variant_signature)
);

CREATE INDEX IF NOT EXISTS idx_pv_entity ON process_variant(entity_type);
CREATE INDEX IF NOT EXISTS idx_pv_conforming ON process_variant(entity_type, is_conforming);

-- Canonical governed lifecycle model (single source of truth for conformance).
-- draft -> submitted -> verified -> published, with rejected reachable from any
-- non-terminal state and published/rejected acting as terminal.
CREATE TABLE IF NOT EXISTS process_model (
    status VARCHAR(50) PRIMARY KEY,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_next JSONB NOT NULL
);

INSERT INTO process_model (status, is_terminal, allowed_next) VALUES
    ('draft',     FALSE, '["submitted","rejected"]'),
    ('submitted', FALSE, '["verified","rejected"]'),
    ('verified',  FALSE, '["published","rejected"]'),
    ('published', TRUE,  '[]'),
    ('rejected',  TRUE,  '[]')
ON CONFLICT (status) DO UPDATE SET
    is_terminal = EXCLUDED.is_terminal,
    allowed_next = EXCLUDED.allowed_next;
