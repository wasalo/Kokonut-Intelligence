-- Forward-deployment (preempt) support for strategic reserves.
-- Adds a preempt band so the monitor can surface a DRAFT forward-deployment
-- proposal BEFORE the hard breach threshold is crossed ("best defense is a
-- good offense"). The proposal remains DRAFT and requires human approval;
-- nothing here performs an autonomous drawdown.

ALTER TABLE strategic_reserve
    ADD COLUMN IF NOT EXISTS preempt_threshold_pct NUMERIC(5,4);

COMMENT ON COLUMN strategic_reserve.preempt_threshold_pct IS
    'Fraction (0-1) of the way to the hard trigger_threshold at which a DRAFT '
    'forward-deployment proposal is surfaced before a breach. NULL disables preempt.';
