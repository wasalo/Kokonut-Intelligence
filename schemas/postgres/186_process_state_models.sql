-- ============================================================
-- 186_process_state_models.sql - Per-entity-type process models
-- ============================================================
-- Generalizes the canonical 5-state process_model (182) into a per-entity-type
-- model so that governed tables with a different state machine (work_item,
-- market_order, metric_value) can be mined, monitored, predicted, and
-- escalated with the same engine. The default '*' model keeps the original
-- 5-state publication vocabulary for all currently-instrumented tables.
--
-- Per-type rows are seeded explicitly here for types that lack a
-- workflow_spec; types that have a registered WorkflowSpec (e.g. work_item)
-- are kept in sync by services.analytics.process_model_sync.

ALTER TABLE process_model DROP CONSTRAINT IF EXISTS process_model_pkey;
ALTER TABLE process_model ADD COLUMN IF NOT EXISTS entity_type VARCHAR(50) NOT NULL DEFAULT '*';
ALTER TABLE process_model ADD COLUMN IF NOT EXISTS is_goal BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE process_model ADD COLUMN IF NOT EXISTS is_initial BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE process_model ADD PRIMARY KEY (entity_type, status);

-- Existing 5 default rows keep entity_type='*'; mark the goal + initial state.
UPDATE process_model SET is_goal = TRUE WHERE entity_type = '*' AND status = 'published';
UPDATE process_model SET is_initial = TRUE WHERE entity_type = '*' AND status = 'draft';

-- Explicit per-type models for types without a workflow_spec.
INSERT INTO process_model (entity_type, status, is_terminal, allowed_next, is_goal, is_initial) VALUES
    -- market_order: pending -> confirmed -> shipped -> delivered (cancelled terminal)
    ('market_order', 'pending',   FALSE, '["confirmed","cancelled"]', FALSE, TRUE),
    ('market_order', 'confirmed', FALSE, '["shipped","cancelled"]',  FALSE, FALSE),
    ('market_order', 'shipped',   FALSE, '["delivered","cancelled"]', FALSE, FALSE),
    ('market_order', 'delivered', TRUE,  '[]',                       TRUE,  FALSE),
    ('market_order', 'cancelled', TRUE,  '[]',                       FALSE, FALSE),
    -- metric_value: draft (unverified) -> verified, mapped from the verified boolean
    ('metric_value', 'draft',   FALSE, '["verified"]', FALSE, TRUE),
    ('metric_value', 'verified', TRUE,  '[]',           TRUE,  FALSE)
ON CONFLICT (entity_type, status) DO UPDATE SET
    is_terminal = EXCLUDED.is_terminal,
    allowed_next = EXCLUDED.allowed_next,
    is_goal = EXCLUDED.is_goal,
    is_initial = EXCLUDED.is_initial;

-- work_item: seeded here to match services/workflow_specs/work_item.py so the
-- model exists immediately after migration; process_model_sync keeps it in sync.
INSERT INTO process_model (entity_type, status, is_terminal, allowed_next, is_goal, is_initial) VALUES
    ('work_item', 'draft',      FALSE, '["assigned","cancelled"]',                  FALSE, TRUE),
    ('work_item', 'assigned',   FALSE, '["in_progress","draft","cancelled"]',       FALSE, FALSE),
    ('work_item', 'in_progress', FALSE, '["blocked","done","cancelled"]',           FALSE, FALSE),
    ('work_item', 'blocked',    FALSE, '["in_progress","cancelled"]',               FALSE, FALSE),
    ('work_item', 'done',       TRUE,  '[]',                                        TRUE,  FALSE),
    ('work_item', 'cancelled',  TRUE,  '[]',                                        FALSE, FALSE)
ON CONFLICT (entity_type, status) DO UPDATE SET
    is_terminal = EXCLUDED.is_terminal,
    allowed_next = EXCLUDED.allowed_next,
    is_goal = EXCLUDED.is_goal,
    is_initial = EXCLUDED.is_initial;
