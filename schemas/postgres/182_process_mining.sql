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
--
-- Keyed by (entity_type, status): the default '*' row holds the original
-- 5-state publication vocabulary; 186 generalizes this to per-entity-type
-- models (work_item, market_order, metric_value, ...).
CREATE TABLE IF NOT EXISTS process_model (
    entity_type VARCHAR(50) NOT NULL DEFAULT '*',
    status VARCHAR(50) NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_next JSONB NOT NULL,
    is_goal BOOLEAN NOT NULL DEFAULT FALSE,
    is_initial BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (entity_type, status)
);

INSERT INTO process_model (entity_type, status, is_terminal, allowed_next, is_goal, is_initial) VALUES
    ('*', 'draft',     FALSE, '["submitted","rejected"]',     FALSE, TRUE),
    ('*', 'submitted', FALSE, '["verified","rejected"]',      FALSE, FALSE),
    ('*', 'verified',  FALSE, '["published","rejected"]',     FALSE, FALSE),
    ('*', 'published', TRUE,  '[]',                           TRUE,  FALSE),
    ('*', 'rejected',  TRUE,  '[]',                           FALSE, FALSE)
ON CONFLICT (entity_type, status) DO UPDATE SET
    is_terminal = EXCLUDED.is_terminal,
    allowed_next = EXCLUDED.allowed_next,
    is_goal = EXCLUDED.is_goal,
    is_initial = EXCLUDED.is_initial;
